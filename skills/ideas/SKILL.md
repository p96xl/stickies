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

## Children

When an idea splits, create the pieces with `--parent <slug>` (or set `parent:` on each).
The child names the parent, never the reverse. `list` nests them; `check` prints
`[n of m children resolved]` and flags a parent whose children are all done.

A parent is finished when its children are - ASK before closing it, then resolve it
`dropped` with `because: superseded by its own children`. Never delete the parent: the
lineage is the answer to "did I ever do that original idea?".

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
- Never capture a question.
- **Do capture work being discussed right now if it will not be FINISHED in this conversation**
  - blocked on something, deferred, or just too big for today. "We are talking about it" is not
  a reason to skip it; a conversation ending is exactly how an idea gets orphaned. Only skip
  capturing the specific task you are actively completing this minute.
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

# Backup and restore (Obsidian MCP, incremental)

The inbox is local files. The vault holds **one note per idea** under `Stickies/`, plus a
small `Stickies/Index.md`. Sync moves through MCP in both directions - never a synced folder -
so it works on any machine with a connector. No vault address is stored in this plugin.

**Only push what changed.** A local cache at `$STICKIES_DIR/.vault-cache/` holds the last
synced copy of each idea, so a one-idea edit costs about 1 KB instead of re-sending the whole
inbox. That difference is the whole point: measured, 426 bytes against 25,122.

**If a vault URL is configured** (`~/.config/stickies/mcp-url`), stickies talks to the vault
ITSELF. Prefer this always - the note content never enters your context:

    stickies push      # sends changed ideas + the index, updates the cache
    stickies pull      # fetches ideas, keeps local files unless --force

You read one summary line. Do NOT call read_note/write_note yourself when these work.

**Fallback, only when no URL is configured** - then you are the transport:

1. `stickies changed` - prints only what needs pushing. Empty means stop.
2. For each name, read `$STICKIES_DIR/<name>` and `write_note` it to `Stickies/<stem>.md`.
3. `stickies index`, `write_note` to `Stickies/Index.md`.
4. `stickies mark` - never skip this, or the next sync re-pushes everything.

**Only ever run `mark` straight after a real push.** It asserts "the vault has this", so
running it on its own makes `changed` report in-sync when nothing was ever sent. If you
suspect the cache is lying, `stickies push --all` resends everything and repairs it.

**Never ask the user to paste the vault URL into the conversation.** It is the credential -
a secret UUID in the path. Tell them to write it to the config file themselves.

`stickies export` / `import` still exist for a single-file snapshot - useful for a one-shot
archive, but it costs the full inbox every time, so prefer `changed` for routine syncing.

Tell the user the counts and the bytes moved. A backup nobody can see the size of is a backup
nobody trusts.
