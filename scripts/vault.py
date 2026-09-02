#!/usr/bin/env python3
"""Minimal MCP client for a FastMCP Streamable-HTTP server. stdlib only.

Exists so `stickies pull` / `push` talk to the vault directly instead of routing
every byte through an assistant's context window. Pulling 13 ideas costs one line
of output here, against ~25 KB when a model has to carry the content itself.

THE URL IS THE CREDENTIAL. These servers authenticate with a secret UUID in the
path, so this module never prints it, never logs it, and never accepts it as a
command-line argument (argv is world-readable via ps). Supply it as:

    ~/.config/stickies/mcp-url     (chmod 600, preferred)
    $STICKIES_MCP_URL              (env fallback)
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

URL_FILE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "stickies" / "mcp-url"
PROTOCOLS = ("2025-06-18", "2024-11-05")


class VaultError(RuntimeError):
    pass


def redact(text):
    """Never let the secret path segment reach a terminal or a log."""
    return re.sub(r"(https?://[^/\s]+)/\S+", r"\1/<redacted>", str(text))


def load_url():
    url = os.environ.get("STICKIES_MCP_URL", "").strip()
    if not url and URL_FILE.is_file():
        if URL_FILE.stat().st_mode & 0o077:
            raise VaultError(f"{URL_FILE} is group/world readable - chmod 600 it first")
        url = URL_FILE.read_text(encoding="utf-8").strip()
    if not url:
        raise VaultError(
            f"no vault URL. Write it to {URL_FILE} (chmod 600) or set $STICKIES_MCP_URL. "
            "Do not paste it into a chat - it is the credential."
        )
    if not url.startswith("https://"):
        raise VaultError("refusing a non-https vault URL - the secret is in the path")
    return url


def _parse(body, content_type):
    """Streamable HTTP answers as plain JSON or as SSE frames. Accept both."""
    if "text/event-stream" in (content_type or ""):
        for line in body.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk:
                    obj = json.loads(chunk)
                    if "result" in obj or "error" in obj:
                        return obj
        raise VaultError("no JSON-RPC payload in the event stream")
    return json.loads(body)


class Vault:
    def __init__(self, url=None, timeout=60):
        self.url = url or load_url()
        self.timeout = timeout
        self.session = None
        self._rpc_id = 0

    def _post(self, payload, extra_headers=None):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        headers.update(extra_headers or {})
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                sid = r.headers.get("Mcp-Session-Id")
                if sid:
                    self.session = sid
                return r.read().decode("utf-8", "replace"), r.headers.get("Content-Type")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            raise VaultError(f"HTTP {e.code} from vault: {redact(detail)}") from None
        except urllib.error.URLError as e:
            raise VaultError(f"cannot reach vault: {redact(e.reason)}") from None

    def _call(self, method, params=None):
        self._rpc_id += 1
        body, ctype = self._post(
            {"jsonrpc": "2.0", "id": self._rpc_id, "method": method, "params": params or {}}
        )
        obj = _parse(body, ctype)
        if "error" in obj:
            raise VaultError(f"{method} failed: {redact(obj['error'])}")
        return obj.get("result", {})

    def connect(self):
        last = None
        for proto in PROTOCOLS:
            try:
                self._call("initialize", {
                    "protocolVersion": proto,
                    "capabilities": {},
                    "clientInfo": {"name": "stickies", "version": "0.4.0"},
                })
                self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
                return self
            except VaultError as e:
                last = e
        raise VaultError(f"handshake failed for {PROTOCOLS}: {last}")

    def tool(self, name, **arguments):
        res = self._call("tools/call", {"name": name, "arguments": arguments})
        if res.get("isError"):
            raise VaultError(f"tool {name} reported an error: {redact(res)}")
        parts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
        text = "\n".join(parts)
        # these servers wrap payloads as {"result": "..."} inside the text block
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and "result" in obj:
                return obj["result"]
        except (ValueError, TypeError):
            pass
        return text

    # --- the three operations stickies actually needs -------------------------
    def read_note(self, path):
        return self.tool("read_note", path=path)

    def write_note(self, path, content):
        return self.tool("write_note", path=path, content=content, overwrite=True)

    def list_folder(self, folder):
        """Paths under a folder, via the tag query the server exposes."""
        out = self.tool("query_notes", tags=["type/idea"], limit=500)
        paths = []
        for line in str(out).splitlines():
            p = line.split("|")[0].strip()
            if p.startswith(folder.rstrip("/") + "/") and p.endswith(".md"):
                paths.append(p)
        return paths
