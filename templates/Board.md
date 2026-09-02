---
tags: [type/index]
---

# Idea Board

Generated. Never edit this file — edit the ideas, or run `/ideas`.
Copy this file into your `STICKIES_DIR`. Requires the Dataview plugin.

---

## Doing

```dataview
TABLE WITHOUT ID file.link AS Idea, last AS "Left", because AS Note
FROM "stickies"
WHERE status = "doing"
SORT file.mtime DESC
```

## Half done — where you left off

```dataview
TABLE WITHOUT ID file.link AS Idea, baseline AS "Started at", last AS "Now"
FROM "stickies"
WHERE check != "" AND baseline != "" AND last != baseline AND last != want
SORT file.mtime DESC
```

## Ready — could start today

```dataview
TABLE WITHOUT ID file.link AS Idea, check AS Check
FROM "stickies"
WHERE status = "ready"
SORT file.mtime ASC
```

## Baking — raw, waiting on one answer

```dataview
TABLE WITHOUT ID file.link AS Idea, created AS Since,
  (date(today) - date(created)).days AS "Days"
FROM "stickies"
WHERE status = "raw"
SORT created ASC
```

## Untouched over 14 days

```dataview
TABLE WITHOUT ID file.link AS Idea, status AS Status,
  round((date(today) - date(file.mtime)).days) AS "Days quiet"
FROM "stickies"
WHERE contains(list("raw", "ready", "doing"), status)
  AND file.mtime < date(today) - dur(14 days)
SORT file.mtime ASC
```

## Resolved — last 30 days

```dataview
TABLE WITHOUT ID file.link AS Idea, status AS How, because AS Why
FROM "stickies"
WHERE contains(list("done", "dropped"), status)
  AND file.mtime > date(today) - dur(30 days)
SORT file.mtime DESC
```
