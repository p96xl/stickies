# stickies

An idea inbox that checks its own state.

You have forty small things in your head. *Rename this to that. Boss didn't like it, change
it back. Half the renames landed and now you don't know which half.* You write them on
sticky notes because sticky notes have zero capture friction. Then you lose track of which
ones you did.

Every todo app fails this the same way: **a checkbox is binary and your reality is a
percentage.** "Half the things got renamed" has no checkbox.

stickies fixes that by not tracking state at all. It **checks** it.

```
HALF DONE (2)
  · Rename PO# to RR# on the device form   [5 left, was 12]   (po-number-rename)
  · Make the QC badge blue                 [2 left, was 3]    (qc-badge-blue)

NOT STARTED (4)
  · Split TODOs.md, MCP will not read it    [1 left]
  ...

^ HALF DONE is where you left off.
```

Nobody ticked a box to produce that.

## How it works

An idea is one small markdown file. If it has a `check:` — a shell command that prints a
number — stickies remembers what that number was the **first time it ever looked**
(`baseline`) and compares:

| | Means |
|---|---|
| `last == want` | **DONE** |
| `last == baseline` | **NOT STARTED** |
| anything between | **HALF DONE** ← where you left off |

`grep -rl 'PO#' src/ \| wc -l` returned 12 the day you wrote the idea down. It returns 5
now. You started and stopped. Nothing had to remember that but the code itself.

Ideas that can't be checked (*"boss didn't like the wording"*) still get captured — they
just show up as NO CHECK, and those are the only ones you have to look at yourself.

## Install

```
/plugin marketplace add p96xl/stickies
/plugin install stickies
```

Then point it at a folder. Anywhere — its own directory, or a folder inside an Obsidian
vault:

```bash
export STICKIES_DIR="$HOME/Documents/ObsidianVault/stickies"   # default: ~/stickies
export STICKIES_STALE_DAYS=14                                   # default: 14
```

Put it in your shell profile, or in `~/.claude/settings.json`:

```json
{ "env": { "STICKIES_DIR": "/home/you/Documents/ObsidianVault/stickies" } }
```

## Using it

**Capture happens on its own.** Mention something that isn't the task at hand — *"we should
also rename that"*, *"that's broken"*, *"remind me to…"* — and it gets filed. You get one
line back, `📥 captured: po-number-rename`, and the conversation carries on. It never stops
to discuss the thing you just mentioned, because that is exactly what orphans the work you
were already doing.

Before writing, it looks for a near-duplicate. If it finds one it asks *"similar to X — same
thing, or different?"* and waits. You decide. Say different and it records why in both
files, so it stops asking.

**`/ideas`** runs the triage: every check, the stale list, and a walk through what needs a
decision — leading with HALF DONE.

**Every session start** it tells you how many ideas have gone quiet. That's it, one line.
You cannot open a session without being reminded they exist, which is the whole anti-orphan
mechanism. It stays silent when nothing is stale.

## The file

```markdown
---
id: 0042
status: raw          # raw | ready | doing | done | dropped
created: 2026-09-02
because: ""          # why it ended: a reason, or [[another-idea]]
check: "grep -rl 'PO#' src/ | wc -l"
want: 0
baseline: ""         # written by the runner. Never edit.
last: ""             # written by the runner. Never edit.
tags: [type/idea]
---

Rename PO# to RR# on the device form.

**Heard while:** talking about the sales-review copy button.
**To be ready:** does this touch the portal form too, or backend only?
```

Under 20 lines, always. They get resolved, not appended to — so no file ever grows into
something your tooling won't read.

### Five statuses

- `raw` — captured, not executable yet. Something is still unknown.
- `ready` — has a check and a finish line. Could be started today.
- `doing` — started.
- `done` — finished.
- `dropped` — over. `because:` says why.

`because:` does the work of three statuses: `"boss changed his mind"` (cancelled),
`"[[idea-0058]]"` (superseded), `"same as [[idea-0012]], merged"` (duplicate). Ideas are
never deleted — a dropped idea with its reason is what stops it being proposed again in
three months.

**Baking is `raw` → `ready`.** The `To be ready:` line holds the one unknown blocking it.
An idea isn't waiting on time, it's waiting on one answer. `/ideas` asks you that question.

## Obsidian

Copy `templates/Board.md` into your `STICKIES_DIR`. Needs the Dataview plugin. Six tables:
Doing, Half done, Ready, Baking, Untouched, Resolved. Generated, never maintained.

## The runner directly

```bash
python3 scripts/stickies.py check          # run every check, print the buckets
python3 scripts/stickies.py stale 21       # live ideas untouched over 21 days
python3 scripts/stickies.py list ready     # everything, or one status
python3 scripts/stickies.py new "text" "heard while"
python3 scripts/stickies.py selftest
```

No dependencies. Python 3.9+.

## What it deliberately doesn't have

No priorities, no due dates, no effort estimates, no graph view, no notifications outside
the terminal, no database. Those are what turn a capture tool into another thing you have
to maintain. Add them when the flat folder is actually the thing hurting.

## Known limits

- **Capture only fires while you're talking to Claude Code.** A note from a hallway
  conversation still starts on paper. The session-start line is a decent prompt to dump
  them in, but it isn't automatic.
- **It will over-capture at first.** Expect to drop a few in the first week.
- **A passing check is evidence, not proof.** `/ideas` asks before marking anything done.
  A check that passes the *first* time it ever runs is reported as SUSPECT CHECK rather
  than DONE — far more often the check is wrong than the work is already finished. This
  caught a real bug on the first idea ever filed: a mangled `grep` pattern matched nothing
  and the runner cheerfully declared 478 open items complete.

MIT.
