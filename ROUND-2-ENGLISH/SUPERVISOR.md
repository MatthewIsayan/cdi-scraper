Run `run-supervised.ps1` to resume the existing English database headlessly.
The scraper keeps its three attempts per ZIP. If it then exits with a timeout,
the supervisor opens a fresh browser after 120, 300, then 3600 seconds, allowing
at most three automatic restarts per supervisor launch. Completed ZIPs are
skipped; an unfinished ZIP starts again and saved licenses are deduplicated.
Persistent pagination bugs can still require a code fix.

Successful exits, other errors, and logged access/verification/rate-limit
messages stop the supervisor for review. Logs are in `logs/supervisor.log` and
the timestamped `logs/supervised-*.log` files.

To prevent another restart, create an empty file named `STOP-SUPERVISOR` in
this folder. This does not interrupt a currently active scraper; it takes
effect when that run exits or during cooldown. Remove it before resuming.
Do not run `run.ps1` alongside the supervisor.
