# Recovery for capped searches

## Adaptive policy (supersedes the batch policy below)

Start with two nearby searches in different directions when available. After both finish, add only one follow-up at a time while the latest two include at least ten new licenses OR a new-license rate of at least five percent. Stop expanding that parent after two consecutive low-yield results. Failed/incomplete searches do not count as low yield and block additional expansion until resolved. Finish all available pages of each selected search; duplicate-heavy early pages are not grounds for abandoning it.

Keep the hard limits: eight follow-ups per parent, two generations, 200 extra searches total. A capped follow-up can expand recursively only if its own yield meets the threshold. Capped areas remain unresolved even when low yield stops recovery.

`exports/cap-recovery.csv` shows parent ZIP, follow-up ZIP, status, distinct records, new licenses, duplicate percentage, and cumulative active search seconds including failed attempts but excluding cooldowns/inter-ZIP pauses. New licenses are attributed to the first search that found them within round two; yield depends on processing order. These are starting thresholds, not proven optimal settings.

Adaptive policy validated with isolated SQLite tests for low-yield stopping, productive expansion, pending-task gating, restart deduplication and hard bounds. Live validation is pending; scraper remains paused.

When a ZIP search ends after at least 300 collected rows, it stays `truncated`.
The scraper automatically queues up to eight additional California ZIP centers within five miles of that ZIP and within 50 miles of 91506. It prefers centers about three miles away, with at least 1.5 miles between selected follow-ups; centers under 0.75 miles away are excluded to avoid effectively identical searches.

Any ZIP already queued or searched is skipped. Follow-ups use the same English and Life/Annuity filters and five-mile directory radius. Agent licenses remain deduplicated within round two. Existing searches are not overwritten or marked complete merely because follow-ups were added.

Recovery can expand through two generations, with at most 200 additional ZIP searches. Tasks and parent/child links are saved in SQLite `cap_recovery`, preserved across restarts and shown by the status command. New tasks are processed during the same run; explicit `--max-zips` test limits still limit the run.

This improves coverage but cannot guarantee recovery of the hidden records. Dense areas may keep hitting 300, nearby centers may expose the same results, or no useful ZIP centers may exist. All capped searches remain listed by status for manual review even after follow-ups finish. Queue completion is not proof of exhaustive collection. More reliable full coverage could require a smaller directory radius (if supported), additional legitimate search filters, or a bulk dataset from CDI.

Validation: TypeScript passed and an isolated SQLite test verified candidate creation, restart deduplication, retention of truncated status and recursive bounds. No live capped-search recovery test has been run yet; round two is paused at the user's request.
