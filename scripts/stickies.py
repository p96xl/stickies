#!/usr/bin/env python3
"""stickies - one file per idea, state is checked not tracked.

Ideas live as small markdown files in $STICKIES_DIR (default ~/stickies).
A check is a shell command that prints one number. want: is the target.
baseline: is what the number was the first time we ever looked.

  last == want                -> DONE
  last == baseline            -> NOT STARTED
  anything between            -> HALF DONE   <- this is "where was I"

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
    """Return (frontmatter dict, body str). Missing/!malformed frontmatter -> ({}, text)."""
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
        new = f'\\1 "{v}"'
        raw, n = pat.subn(new, raw, count=1)
        if not n:  # key absent - insert before closing delimiter
            raw = re.sub(r"\n---\n", f'\n{k}: "{v}"\n---\n', raw, count=1)
    path.write_text(raw, encoding="utf-8")


def ideas():
    if not INBOX.is_dir():
        return []
    out = []
    for p in sorted(INBOX.glob("*.md")):
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
    buckets = {"DONE": [], "HALF DONE": [], "NOT STARTED": [], "BROKEN CHECK": [], "NO CHECK": []}
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
        if base is None:  # first ever look - this is the starting line
            base = got
            write_fm(path, {"baseline": got})
        write_fm(path, {"last": got})
        if got == want:
            bucket, note = "DONE", "check passes"
        elif got == base:
            bucket, note = "NOT STARTED", f"{got} left"
        else:
            bucket, note = "HALF DONE", f"{got} left, was {base}"
        buckets[bucket].append((name, path.stem, note))

    for label in ("HALF DONE", "NOT STARTED", "BROKEN CHECK", "NO CHECK", "DONE"):
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


def cmd_new(args):
    if not args:
        print("usage: stickies.py new \"<idea text>\" [heard-while]", file=sys.stderr)
        return 2
    text = args[0]
    heard = args[1] if len(args) > 1 else "(not recorded)"
    INBOX.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for _, fm, _ in ideas() if (m := re.match(r"^(\d+)$", str(fm.get("id", ""))))]
    nid = f"{max(nums, default=0) + 1:04d}"
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or nid
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
    import tempfile

    global INBOX
    with tempfile.TemporaryDirectory() as d:
        INBOX = Path(d)
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

        assert run_check("echo not-a-number") is None
        assert run_check("exit 1") is None

        # resolved ideas drop out of the live set
        write_fm(p, {"status": "done"})
        assert [i for i in ideas() if i[1]["status"] in LIVE] == []
        # a file with no frontmatter must not crash the walk
        (INBOX / "junk.md").write_text("no frontmatter here", encoding="utf-8")
        assert len(ideas()) == 1
    print("selftest ok")
    return 0


def main():
    cmds = {"check": cmd_check, "stale": cmd_stale, "list": cmd_list, "new": cmd_new,
            "selftest": lambda a: selftest()}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(f"usage: stickies.py {{{'|'.join(cmds)}}} [args]   (inbox: {INBOX})", file=sys.stderr)
        return 2
    return cmds[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
