# Run reports

One report per live run: what the run stored, as the run itself decided it. The reports are
written by code, not by hand, so the numbers match the database
([docs/design/learning.md](../../docs/design/learning.md), T081). What each run taught us goes in
[docs/learning-log.md](../../docs/learning-log.md).

```bash
# in the API container (or anywhere with DATABASE_URL set): no model call, no write, no cost
python -m app.verify.report <project-id> [--target storyboard|comic] > eval/runs/<date>-<script>.md
```

Find a project by its id, never by its title: two uploads of one script share a title.

| Date | Script | Settings | Accepted | Drawings | Report |
|---|---|---|---|---|---|
| 2026-10-11 | the-red-kite | klein, 3 attempts, after T079 + T080 | 16 of 21 | 38 | [report](2026-10-11-the-red-kite.md) |
| 2026-10-11 | sipho-and-siphokazi | klein, 3 attempts, after T079 + T080 | 7 of 30 | 82 | [report](2026-10-11-sipho-and-siphokazi.md) |
