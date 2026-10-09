# Restore round one

This folder contains the actual source files and settings used at the end of round one, including uncommitted code changes. It also includes the main and 91506 CSVs, completed SQLite database, dependency lockfile, TypeScript configuration, project documentation, ZIP plan and available overnight log.

## Safest restoration: separate folder

Copy this entire snapshot to a new working folder. In that copy:

1. Create `data` and `exports` folders.
2. Move the root-level `agents.db` into `data/agents.db`.
3. Move the root-level CSV files into `exports`.
4. Run `npm ci` to install the locked dependency versions.
5. Run `npm run status` to verify the saved 402 unique agents and 128 completed searches.

`npm run scrape` then uses the saved settings and resumes only unfinished ZIPs. With the saved completed database, it should have nothing left to search. For a completely fresh repeat, use a separate copy without the saved database; keep this snapshot's database intact.

To restore into the existing project instead, first stop its scraper and back up its current code/settings/database. Copy this snapshot's `src`, configuration and dependency files back, and restore `agents.db` to `data/agents.db` only if you also intend to restore round-one data.

## Saved settings

- Center: 91506
- Coverage: 50 miles
- ZIP spacing: 4 miles
- Directory search radius: 5 miles
- Insurance: LIFE_ANU
- Language: ARMN
- Headless: true
- Page pause: 2–4 seconds
- ZIP pause: 5–10 seconds
- Attempts per ZIP: 3

Browser binaries, browser profiles/cookies, `node_modules`, Git history and Windows power settings are not included. Installed Chrome is used where available; otherwise install Chromium with `npx playwright install chromium`. Requires a compatible Node.js version with SQLite support (the run used Node 24).

`README.md` is the project's original documentation. It may contain older defaults; `config.json` is the authoritative saved configuration. Keep this snapshot unchanged when starting round two.
