#!/usr/bin/env python3
"""stickies - one file per idea, state is checked not tracked.

Ideas live as small markdown files in $STICKIES_DIR (default ~/stickies).
A check is a shell command that prints one number. want: is the target.
baseline: is what the number was the first time we ever looked.

  last == want                -> DONE
  last == baseline            -> NOT STARTED
  anything between            -> HALF DONE   <- this is "where was I"

Backup runs through an Obsidian MCP in BOTH directions: `export` emits one
lossless document for Claude to write into the vault, `import` rebuilds the
inbox from that document on any machine. No filesystem sync required, and no
vault address is stored here - Claude uses whatever connector is configured.

ponytail: no yaml dep, we control the file format so a line parser is enough.
"""
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

INBOX = Path(os.environ.get("STICKIES_DIR", Path.home() / "stickies")).expanduser()
LIVE = ("raw", "ready", "doing")


def cache_dir():
    """Last-known vault contents, so sync moves only what changed (~1 KB, not ~25 KB).

    A function, not a constant: selftest reassigns INBOX, and a module-level CACHE
    computed at import time kept pointing at the real inbox and wrote test files into it.
    """
    return INBOX / ".vault-cache"

BEGIN, END, FILE = "<!-- stickies:begin -->", "<!-- stickies:end -->", "<!-- stickies:file "

TEMPLATE = """---
id: {id}
status: raw
created: {created}
because: ""
check: ""
want: 0
baseline: ""
last: ""
tags: [type/idea]
---

{text}

**Heard while:** {heard}
**To be ready:** what is still unknown before this can be started?
"""


def parse(path):
    """Return (frontmatter dict, body str). Missing/malformed frontmatter -> ({}, text)."""
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, re.S)
    if not m:
        return {}, raw
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, m.group(2)


def write_fm(path, updates):
    """Rewrite only the named frontmatter keys, leaving body and key order intact."""
    raw = path.read_text(encoding="utf-8")
    for k, v in updates.items():
        pat = re.compile(rf"^({re.escape(k)}:).*$", re.M)
        raw, n = pat.subn(f'\\1 "{v}"', raw, count=1)
        if not n:  # key absent - insert before closing delimiter
            raw = re.sub(r"\n---\n", f'\n{k}: "{v}"\n---\n', raw, count=1)
    path.write_text(raw, encoding="utf-8")


def ideas():
    if not INBOX.is_dir():
        return []
    out = []
    for p in sorted(INBOX.glob("*.md")):  # top level only - .vault-cache is a subdir
        if p.name.lower() in ("board.md", "readme.md", "index.md"):
            continue
        fm, body = parse(p)
        if fm:
            out.append((p, fm, body))
    return out


def title(body):
    for line in body.strip().splitlines():
        if line.strip():
            return line.strip()
    return "(empty)"


def run_check(cmd):
    """Run a check, return int or None. A check that errors is not a done check."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None
    tail = r.stdout.strip().splitlines()
    if not tail:
        return None
    try:
        return int(tail[-1].strip())
    except ValueError:
        return None


def cmd_check(args):
    buckets = {"DONE": [], "HALF DONE": [], "NOT STARTED": [], "SUSPECT CHECK": [],
               "BROKEN CHECK": [], "NO CHECK": []}
    for path, fm, body in ideas():
        if fm.get("status") not in LIVE:
            continue
        name, chk = title(body), fm.get("check", "")
        if not chk:
            buckets["NO CHECK"].append((name, path.stem, ""))
            continue
        got = run_check(chk)
        if got is None:
            buckets["BROKEN CHECK"].append((name, path.stem, chk))
            continue
        want = int(fm.get("want") or 0)
        base = fm.get("baseline")
        base = int(base) if str(base).strip().lstrip("-").isdigit() else None
        first_look = base is None
        if first_look:  # this is the starting line
            base = got
            write_fm(path, {"baseline": got})
        write_fm(path, {"last": got})
        if got == want and first_look:
            # A check that passes the very first time it runs is more often a broken
            # check than a finished idea. Silently reporting DONE here is how the whole
            # system loses your trust, so make a human look at it instead.
            bucket, note = "SUSPECT CHECK", "passes on its first ever run - verify it"
        elif got == want:
            bucket, note = "DONE", "check passes"
        elif got == base:
            bucket, note = "NOT STARTED", f"{got} left"
        else:
            bucket, note = "HALF DONE", f"{got} left, was {base}"
        buckets[bucket].append((name, path.stem, note))

    for label in ("HALF DONE", "NOT STARTED", "SUSPECT CHECK", "BROKEN CHECK", "NO CHECK", "DONE"):
        rows = buckets[label]
        if not rows:
            continue
        print(f"\n{label} ({len(rows)})")
        for name, stem, note in rows:
            print(f"  · {name}" + (f"  [{note}]" if note else "") + f"  ({stem})")
    if buckets["HALF DONE"]:
        print("\n^ HALF DONE is where you left off.")
    return 0


def cmd_stale(args):
    days = int(args[0]) if args else 14
    now = datetime.now().timestamp()
    rows = [
        (path, fm, body)
        for path, fm, body in ideas()
        if fm.get("status") in LIVE and (now - path.stat().st_mtime) > days * 86400
    ]
    if not rows:
        print(f"nothing untouched over {days} days.")
        return 0
    print(f"{len(rows)} untouched over {days} days:")
    for path, fm, body in sorted(rows, key=lambda r: r[0].stat().st_mtime):
        age = int((now - path.stat().st_mtime) / 86400)
        print(f"  · [{fm.get('status'):<5}] {title(body)}  ({age}d, {path.stem})")
    return 0


def cmd_list(args):
    want = args[0] if args else None
    for path, fm, body in ideas():
        st = fm.get("status", "?")
        if want and st != want:
            continue
        because = fm.get("because") or ""
        print(f"[{st:<7}] {title(body)}" + (f"  <- {because}" if because else "") + f"  ({path.stem})")
    return 0


def cmd_export(args):
    """Emit the whole inbox as ONE lossless document for the vault.

    Every idea file goes in verbatim between HTML-comment delimiters, so `import`
    reproduces it byte for byte on any machine. ponytail: comments, not code fences -
    an idea body can contain backticks and a fence war is not worth the cleverness.
    """
    rows = ideas()
    live = [r for r in rows if r[1].get("status") in LIVE]
    out = ["---", "tags: [type/index, domain/personal]", "---", "",
           "# Stickies - Inbox Snapshot", "",
           f"{len(rows)} ideas ({len(live)} live), exported {date.today()} from `{INBOX}`.",
           "",
           "**Do not edit this note.** It is a backup. To restore on any machine, ask Claude",
           "to read this note back and run `stickies import`.", "", "## Contents", ""]
    for path, fm, body in sorted(rows, key=lambda r: (r[1].get("status", ""), r[0].name)):
        out.append(f"- `{fm.get('status', '?'):<7}` {title(body)}")
    out += ["", BEGIN, ""]
    for path, fm, body in rows:
        out += [FILE + path.name + " -->", path.read_text(encoding="utf-8").rstrip(), ""]
    out += [END, ""]
    print("\n".join(out))
    return 0


def cmd_import(args):
    """Rebuild the inbox from an exported snapshot. Never overwrites without --force."""
    if not args:
        print('usage: stickies.py import <snapshot.md> [--force]', file=sys.stderr)
        return 2
    text = Path(args[0]).expanduser().read_text(encoding="utf-8")
    force = "--force" in args
    if BEGIN not in text or END not in text:
        print("not a stickies snapshot - no delimiters found", file=sys.stderr)
        return 1
    payload = text.split(BEGIN, 1)[1].rsplit(END, 1)[0]
    INBOX.mkdir(parents=True, exist_ok=True)
    wrote = skipped = 0
    for chunk in payload.split(FILE)[1:]:
        name, _, content = chunk.partition(" -->\n")
        name = name.strip()
        # the snapshot is data, not a trusted source of paths
        if not name.endswith(".md") or "/" in name or "\\" in name or name.startswith("."):
            print(f"  skipped suspicious name: {name!r}", file=sys.stderr)
            continue
        dest = INBOX / name
        if dest.exists() and not force:
            skipped += 1
            continue
        body_text = content.strip() + "\n"
        dest.write_text(body_text, encoding="utf-8")
        cache_dir().mkdir(parents=True, exist_ok=True)
        (cache_dir() / name).write_text(body_text, encoding="utf-8")
        wrote += 1
    print(f"imported {wrote} idea(s) into {INBOX}"
          + (f", skipped {skipped} already present (use --force to overwrite)" if skipped else ""))
    return 0


def cmd_changed(args):
    """Names of ideas that differ from the last synced vault copy. Empty = in sync."""
    cache_dir().mkdir(parents=True, exist_ok=True)
    live = {p.name: p.read_text(encoding="utf-8") for p, _, _ in ideas()}
    cached = {f.name: f.read_text(encoding="utf-8") for f in cache_dir().glob("*.md")}
    push = sorted(n for n, c in live.items() if cached.get(n) != c)
    gone = sorted(n for n in cached if n not in live)
    for n in push:
        print(("NEW   " if n not in cached else "CHANGED ") + n)
    for n in gone:
        print("LOCAL-ONLY-DELETED " + n)
    if not push and not gone:
        print("in sync with the vault cache")
    return 0


def cmd_mark(args):
    """Record that named ideas (or all) now match the vault. Run AFTER a successful push."""
    cache_dir().mkdir(parents=True, exist_ok=True)
    live = {p.name: p for p, _, _ in ideas()}
    names = [a for a in args if not a.startswith("-")] or list(live)
    n = 0
    for name in names:
        src = live.get(name)
        if not src:
            print(f"  no such idea: {name}", file=sys.stderr)
            continue
        (cache_dir() / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        n += 1
    print(f"cache updated for {n} idea(s)")
    return 0


def cmd_index(args):
    """The small index note for the vault - names and statuses only, no bodies."""
    rows = ideas()
    live = [r for r in rows if r[1].get("status") in LIVE]
    print("---")
    print("tags: [type/index, domain/personal]")
    print("---")
    print()
    print("# Stickies - Index")
    print()
    print(f"{len(rows)} ideas, {len(live)} live. Synced {date.today()}.")
    print()
    print("One note per idea in this folder. Restore with `stickies import`.")
    print()
    for path, fm, body in sorted(rows, key=lambda r: (r[1].get("status", ""), r[0].name)):
        print(f"- `{fm.get('status', '?'):<7}` [[{path.stem}]] - {title(body)}")
    return 0


def cmd_new(args):
    if not args:
        print('usage: stickies.py new "<idea text>" [heard-while]', file=sys.stderr)
        return 2
    text = args[0]
    heard = args[1] if len(args) > 1 else "(not recorded)"
    INBOX.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for _, fm, _ in ideas() if (m := re.match(r"^(\d+)$", str(fm.get("id", ""))))]
    nid = f"{max(nums, default=0) + 1:04d}"
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())[:48].strip("-") or nid
    path = INBOX / f"{slug}.md"
    if path.exists():
        path = INBOX / f"{slug}-{nid}.md"
    path.write_text(
        TEMPLATE.format(id=nid, created=date.today().isoformat(), text=text, heard=heard),
        encoding="utf-8",
    )
    print(path)
    return 0


def selftest():
    import contextlib
    import io
    import tempfile

    global INBOX
    with tempfile.TemporaryDirectory() as d:
        INBOX = Path(d) / "inbox"
        cmd_new(["Rename PO# to RR#", "testing"])
        p = next(INBOX.glob("*.md"))
        fm, body = parse(p)
        assert fm["status"] == "raw" and fm["id"] == "0001", fm
        assert title(body) == "Rename PO# to RR#", title(body)

        # first look records the starting line, and 12 != want 0 -> NOT STARTED
        write_fm(p, {"check": "echo 12", "want": 0})
        cmd_check([])
        fm, _ = parse(p)
        assert fm["baseline"] == "12" and fm["last"] == "12", fm

        # moved off the starting line but not to zero -> HALF DONE
        write_fm(p, {"check": "echo 5"})
        cmd_check([])
        fm, _ = parse(p)
        assert fm["baseline"] == "12" and fm["last"] == "5", fm

        # reached want -> DONE, and baseline is never overwritten
        write_fm(p, {"check": "echo 0"})
        cmd_check([])
        fm, _ = parse(p)
        assert fm["baseline"] == "12" and fm["last"] == "0", fm

        # a check that passes on its first ever run is suspect, not done
        cmd_new(["Already true", "t"])
        p2 = next(x for x in INBOX.glob("*.md") if x != p)
        write_fm(p2, {"check": "echo 0", "want": 0})
        cmd_check([])
        fm2, _ = parse(p2)
        assert fm2["baseline"] == "0" and fm2["last"] == "0", fm2
        write_fm(p2, {"status": "dropped"})

        # export -> import must reproduce every file byte for byte
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_export([])
        snap = buf.getvalue()
        assert "# Stickies - Inbox Snapshot" in snap and BEGIN in snap, snap[:300]
        before = {f.name: f.read_text() for f in INBOX.glob("*.md")}
        snapfile = Path(d) / "snap.txt"
        snapfile.write_text(snap)
        for f in INBOX.glob("*.md"):
            f.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_import([str(snapfile)])
        after = {f.name: f.read_text() for f in INBOX.glob("*.md")}
        assert after == before, f"round trip lost data: {set(before) ^ set(after)}"
        # a second import must not clobber what is already there
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_import([str(snapfile)])
        assert "skipped 2" in out.getvalue(), out.getvalue()

        # changed/mark: everything is new until marked, then nothing is.
        # import seeds the cache, so clear it first to test the from-scratch path.
        for f in cache_dir().glob("*.md"):
            f.unlink()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_changed([])
        assert "NEW" in out.getvalue(), out.getvalue()
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_mark([])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_changed([])
        assert "in sync" in out.getvalue(), out.getvalue()
        # touching one idea makes exactly that one show as changed
        write_fm(p, {"status": "doing"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_changed([])
        lines = [l for l in out.getvalue().splitlines() if l.strip()]
        assert len(lines) == 1 and p.name in lines[0], lines
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_mark([])
        # the cache must never be counted as an idea
        assert len(ideas()) == 2, len(ideas())

        assert run_check("echo not-a-number") is None
        assert run_check("exit 1") is None

        # resolved ideas drop out of the live set
        write_fm(p, {"status": "done"})
        assert [i for i in ideas() if i[1]["status"] in LIVE] == []
        # a file with no frontmatter must not crash the walk
        (INBOX / "junk.md").write_text("no frontmatter here", encoding="utf-8")
        assert len(ideas()) == 2
        # slug must not keep a dash left behind by truncation
        cmd_new(["x" * 60 + " tail", "t"])
        assert not any(f.stem.endswith("-") for f in INBOX.glob("*.md"))
    print("selftest ok")
    return 0


def main():
    cmds = {"check": cmd_check, "stale": cmd_stale, "list": cmd_list, "new": cmd_new,
            "export": cmd_export, "import": cmd_import,
            "changed": cmd_changed, "mark": cmd_mark, "index": cmd_index,
            "selftest": lambda a: selftest()}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(f"usage: stickies.py {{{'|'.join(cmds)}}} [args]   (inbox: {INBOX})", file=sys.stderr)
        return 2
    return cmds[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
