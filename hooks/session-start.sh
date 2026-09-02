#!/usr/bin/env bash
# Every session start, say how many ideas have gone quiet. Nothing else.
# ponytail: find only, no checks run here - a check can ssh or grep a whole repo,
# and nothing that shells out belongs in session startup. Checks run on /ideas.
set -euo pipefail

DIR="${STICKIES_DIR:-$HOME/stickies}"
DAYS="${STICKIES_STALE_DAYS:-14}"

[ -d "$DIR" ] || exit 0

# Live ideas only. A resolved idea is allowed to sit there forever.
count=0
while IFS= read -r f; do
  grep -qE '^status:[[:space:]]*"?(raw|ready|doing)"?[[:space:]]*$' "$f" && count=$((count + 1))
done < <(find "$DIR" -maxdepth 1 -name '*.md' -mtime "+$DAYS" 2>/dev/null)

[ "$count" -gt 0 ] || exit 0

msg="$count idea(s) untouched over $DAYS days. Run /ideas."
# additionalContext -> Claude knows. systemMessage -> the user sees it.
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":%s,"systemMessage":%s}}\n' \
  "\"There are $count stickies ideas untouched for over $DAYS days in $DIR. Mention this once, briefly, and offer /ideas. Do not list them unless asked.\"" \
  "\"📥 $msg\""
