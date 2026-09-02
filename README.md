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

## Making capture reliable — the CLAUDE.md rule

The `ideas` skill knows *how* to capture. But a skill fires when it looks relevant, and
passive capture has to fire while you are busy with something else entirely — which is
exactly when it won't trigger on its own.

Paste this into your `CLAUDE.md` (`~/.claude/CLAUDE.md` for every project, or a
project-level one). This is the part that makes it actually work:

```markdown
## Idea capture (stickies)

While working, if the user states an intent that is NOT the task at hand — a rename, a fix,
a complaint, "we should also...", "remind me to...", "that's broken", "I need to change X"
— capture it to the stickies inbox immediately, before continuing.

1. First look for a near-duplicate: `semantic_search` if an Obsidian MCP is available,
   otherwise `grep -ril "<key words>" "$STICKIES_DIR"`.
2. If anything looks like the same idea, DO NOT create a file. Say:
   "Similar to <existing idea> — same thing, or different?" and wait. The user decides.
   If different, write the new file AND add one line to both saying why they differ.
   If same, touch the existing file (resets its staleness clock) and note the new wording.
3. Otherwise create it: `stickies new "<idea>" "<heard while>"`, then fill in
   `check:` / `want:` if a shell check is possible, and the `**To be ready:**` line
   with the one unknown blocking it.

Rules:
- Silent. ONE line at the end of the reply: `📥 captured: <name>`. Nothing more.
- NEVER derail the current task to discuss the captured idea. That is the exact behaviour
  that orphans the work already in progress.
- Never capture a question.
- DO capture work being discussed right now if it will not be FINISHED in this
  conversation - blocked, deferred, or too big for today. Only skip the specific task
  you are actively completing this minute.
- Always write a real "Heard while:" value. Weeks later it is the only context left.
- A check must print how much is LEFT (`grep -c ... `, `... | wc -l`) with `want: 0`.
  Leave it empty rather than invent a check that does not work.
```

### Put the runner on your PATH first

The plugin caches under a versioned directory, so any path you write down breaks on the
next update. Drop this in `~/.local/bin/stickies` and `chmod +x` it:

```bash
#!/usr/bin/env bash
set -euo pipefail
R=$(ls -d "$HOME"/.claude/plugins/cache/stickies/stickies/*/scripts/stickies.py 2>/dev/null | sort -V | tail -1 || true)
[ -n "$R" ] || R="$HOME/src/stickies/scripts/stickies.py"   # fallback: your clone
exec python3 "$R" "$@"
```

Now `stickies check` works from anywhere and survives every version bump.

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

## Obsidian (optional)

If your `STICKIES_DIR` is inside an Obsidian vault, copy `templates/Board.md` next to your
ideas. Needs the Dataview plugin. Six tables: Doing, Half done, Ready, Baking, Untouched,
Resolved. Generated, never maintained.

Dataview can only query files inside the vault, so this is only for people who keep their
inbox there. **If your vault is read-only or sync-managed, keep the inbox outside it** and
use the terminal — `/ideas` and the session-start line are the real interface anyway. The
checks can still read anything on disk, vault included.

## The runner directly

```bash
stickies check          # run every check, print the buckets
stickies stale 21       # live ideas untouched over 21 days
stickies list ready     # everything, or one status
stickies new "text" "heard while"
stickies export > snapshot.md
stickies import snapshot.md
stickies selftest
```

No dependencies. Python 3.9+.


## Children

An idea that splits gets children. The **child** names its parent, so the parent never has a
list to keep in step:

```yaml
parent: "rescope-cloudflare-rules"     # or: stickies new "..." --parent <slug>
```

`list` nests them. `check` rolls progress up:

```
PARENTS (1)
  - Rescope Cloudflare rules   [8 of 12 children resolved]
```

A parent is finished when its children are. When they all resolve, `check` says
`all children resolved, close it?` - it asks, it does not close anything for you, on the same
principle as a passing check being evidence rather than proof.

This is the case a flat todo list handles worst: one idea becomes many, the original never
gets ticked, and months later nobody can tell whether it happened. Here the original stays
put with its lineage attached, and `dropped ... because superseded by its own children` is a
real, readable outcome.

## Backup and restore

The inbox is local files. The vault copy is the backup, and it travels **through the Obsidian
MCP in both directions** - not through a synced folder - so it works on any machine with the
connector, and no vault address is ever stored in this repo.

```bash
stickies push         # send changed ideas straight to the vault over MCP
stickies push --all   # resend everything (repairs a stale cache)
stickies pull         # fetch ideas from the vault
stickies changed      # only the ideas that differ from the last vault sync
stickies mark         # record that the cache now matches the vault
stickies index        # the small index note for the vault
stickies export > snapshot.md     # one-file archive (costs the whole inbox)
stickies import snapshot.md       # rebuild from a snapshot
```

`push` and `pull` speak MCP themselves, so **the content never passes through an
assistant's context** - pulling the whole inbox costs one line of output instead of ~25 KB.
It also means you can sync from your own terminal with no assistant involved.

### Pointing it at your vault

FastMCP Streamable-HTTP servers commonly authenticate with a **secret UUID in the URL path**.
That URL *is* the credential, so stickies never accepts it as a command-line argument (argv is
visible to `ps`), never logs it, and redacts it from every error message.

```bash
mkdir -p ~/.config/stickies
printf 'https://your-server/mcp/YOUR-SECRET\n' > ~/.config/stickies/mcp-url
chmod 600 ~/.config/stickies/mcp-url
```

`$STICKIES_MCP_URL` works too. Plain `http://` is refused. A config file with group or world
read permissions is refused. Do not paste the URL into a chat window.

Sync is **incremental**. A local cache under `$STICKIES_DIR/.vault-cache/` remembers what the
vault last received, so editing one idea moves ~1 KB instead of the whole inbox - measured,
426 bytes against 25,122. The vault holds one small note per idea rather than one large file,
which also keeps every file comfortably readable over MCP.

The snapshot is lossless - each idea file is embedded verbatim between HTML-comment
delimiters, so `check:` commands and baselines survive the round trip. A prose summary would
quietly drop them, which is how a backup turns out to be worthless on the day you need it.
`import` refuses to overwrite existing files unless you pass `--force`.

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
