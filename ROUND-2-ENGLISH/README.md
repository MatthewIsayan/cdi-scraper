# Round 2 — English

Fresh collection begun October 8, 2026. English (`ENGL`), Life and Annuity (`LIFE_ANU`), 50 miles around ZIP 91506. Same 128 search centers with four-mile spacing and five-mile directory searches.

Database: `data/agents.db`. Live CSV: `exports/cdi-agents.csv`. License numbers are deduplicated within this round only; round-one agents are not excluded.

Run `./run.ps1` to start/resume and `./status.ps1` for status. The scripts use the parent project's source code and installed dependencies, but all data, CSVs, logs, browser profile and configuration are stored in this folder.

Timing: 1–2 seconds between pages, 3–5 seconds between ZIPs. Error waits and three-attempt limit are unchanged. Headless mode enabled. Raw collected prospects are not recruiting-screen approvals.

Any ZIP reaching the site's 300-result limit is incomplete (`truncated`), even if all available groups have been collected. Spaced search centers provide approximate geographic coverage; do not equate queue completion with exhaustive results.
