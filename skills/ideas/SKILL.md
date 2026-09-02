---
name: ideas
description: Capture, triage and resolve small ideas and tasks so none get orphaned. Use when the user says "ideas", "/ideas", "where was I", "what was I working on", "what's still open", "triage my ideas", "what did I forget", or asks what state a half-finished task is in. Also the reference for how to capture an idea mid-conversation into the stickies inbox.
---

# stickies — the idea inbox

Ideas are small markdown files, one per idea, in `$STICKIES_DIR` (default `~/stickies`).
State is **checked, not tracked**. Nobody ever ticks a box by hand.

Runner: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/stickies.py <command>`

| Command | Does |
|---|---|
| `check` | Runs every check. Prints DONE / HALF DONE / NOT STARTED / BROKEN CHECK / NO CHECK. |
| `stale [days]` | Live ideas untouched over N days (default 14). |
| `list [status]` | Everything, or one status. |
| `new "<text>" "<heard while>"` | Creates an idea file, prints its path. |

## The file

```markdown
---
id: 0042
status: raw          # raw | ready | doing | done | dropped
created: 2026-09-02
because: ""          # why it ended: a reason, or [[another-idea]]
check: ""            # shell command printing ONE number
want: 0              # the number that means finished
baseline: ""         # written by the runner on first look. Never edit.
last: ""             # written by the runner. Never edit.
tags: [type/idea]
---

One line saying what the idea is.

**Heard while:** what we were doing when it came up.
**To be ready:** the one unknown blocking it. Empty means it is ready.
```

Keep every file under ~20 lines. They get resolved, not appended to.

## The five statuses

- `raw` — captured, not yet executable. Something is still unknown.
- `ready` — has a check and a clear finish line. Could be started today.
- `doing` — started.
- `done` — finished.
- `dropped` — over. `because:` says why.

`because:` covers cancelled (`"boss changed his mind"`), superseded (`"[[idea-0058]]"`)
and duplicate (`"same as [[idea-0012]], merged"`). One field, three meanings, no extra machinery.

---

# Capturing (do this without being asked)

When the user states an intent that is **not** the task at hand — a rename, a fix, a
complaint, "we should also…", "remind me to…", "that's broken", "I need to change X" —
capture it. Do not wait to be told.

**Before writing, check for a near-duplicate.**

1. If an Obsidian MCP with `semantic_search` is available, search the idea text there.
2. Otherwise `grep -ril "<key words>" "$STICKIES_DIR"`.

If anything looks like the same idea, **do not create the file**. Say exactly this shape:

> Similar to *[existing idea]* — same thing, or different?

Then wait. The user decides. If they say different, write the new file AND add one line to
both files saying why they are not the same, so this is not asked again. If they say same,
touch the existing file instead (which resets its staleness clock) and note the new wording.

**Rules of capture**

- Silent. One line at the end of your reply: `📥 captured: <name>`. Nothing more.
- Never derail the current task to discuss a captured idea. That is the exact behaviour
  that orphans the original work.
- Never capture a question, or the thing you are already doing.
- Write a real `**Heard while:**` value. Six weeks later it is the only context left.
- Add a `check:` if you can think of one. A `grep -c ... ` or `grep -rl ... | wc -l` that
  prints how much is LEFT to do, with `want: 0`. An idea with a check never needs a human
  to remember its state. Leave it empty rather than invent a check that does not work.

---

# Triage (`/ideas`)

Run `check` and `stale` first. Then walk the user through, in this order:

1. **HALF DONE** — lead with this. It is the answer to "where was I". For each, say what
   is left, offer to finish it now.
2. **DONE** — the check passes. Ask to confirm, then set `status: done`. Never set it from
   the check alone; a passing check is evidence, not proof.
3. **BROKEN CHECK** — the check errors or prints no number. It is worthless. Fix or clear it.
4. **Stale `raw`** — read the `**To be ready:**` line back to the user as a direct question.
   One answer promotes it to `ready`. This is how an idea bakes: it is not waiting on time,
   it is waiting on one answer.
5. **Stale `ready`/`doing`** — ask the blunt question: still real? If not, `dropped` with a
   `because:`.
6. **Near-duplicates across the whole inbox** — flag pairs, let the user adjudicate.

Keep it to a handful of items per pass. A triage that lists forty things gets abandoned,
which is the failure this whole system exists to prevent.

## Resolving

Edit frontmatter only — `status:` and `because:`. Never delete an idea file. A `dropped`
idea with its reason is what stops the same idea being proposed again in three months.

---

# Backup and restore (Obsidian MCP, both directions)

The inbox lives on local disk. The vault copy is the backup, and it moves **through MCP in
both directions** - never through a synced folder, so it works on any machine where an
Obsidian MCP is configured. No vault address is stored in this plugin.

**Back up** - do this at the end of a triage pass, or whenever several ideas changed:

1. `stickies export > /tmp/stickies-snapshot.md`
2. Read that file and `write_note` it to `Stickies/Inbox.md` in the vault.

The snapshot is lossless: every idea file is embedded verbatim between
`<!-- stickies:file NAME.md -->` delimiters, so nothing is lost - including `check:` commands,
which a prose summary would drop.

**Restore** - on a new machine, or after losing the inbox:

1. `read_note` on `Stickies/Inbox.md`.
2. Write what comes back to a local file.
3. `stickies import /tmp/stickies-snapshot.md`

Import never overwrites an existing idea file unless `--force` is passed, so running it
against a populated inbox is safe and only fills in what is missing.

Tell the user the counts after either direction. A backup nobody can see the size of is a
backup nobody trusts.
