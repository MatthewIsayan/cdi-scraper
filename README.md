# Armenian Life and Annuity agent search

Pulls public California Department of Insurance "Find an Agent" results for Armenian-speaking Life and Annuity agents. Each search is limited to 5 miles. ZIP codes are spaced around 91506 so a single search does not run into the site's 300-row cap and miss people.

Agents are stored in `data/agents.db`. The same license is never inserted twice. `exports/armenian-life-annuity-agents.csv` is rewritten after every page of results, while the scrape is still running. `npm run export` writes that same file on demand.

## Setup

```powershell
npm install
npx playwright install chromium
```

Chrome, if it is installed, is used automatically. The Chromium download is the fallback.

## Run

```powershell
npm run grid
npm run scrape
```

Leave the browser window alone while it works. It types the ZIP, pauses, and clicks Next the way a person would. Closing the window or pressing Ctrl+C is safe: finished ZIP codes stay finished, and the next run continues the rest.

If the Department of Insurance session expires, the scraper opens a fresh search page and retries that ZIP. Three failed attempts on the same ZIP stop the run. Start it again and that ZIP is picked up first.

In a second terminal, at any time:

```powershell
npm run export
npm run status
```

## Settings

Edit `config.json`.

- `coverageMiles` is how far from 91506 the grid reaches. Default is 15.
- `gridSpacingMiles` is how far apart the ZIP codes are. Default is 4, with each search still set to 5 miles so the circles overlap.
- `headless` stays false so the browser is visible.

Useful test flags:

```powershell
$env:MAX_ZIPS = "1"
$env:MAX_PAGES = "2"
$env:HEADLESS = "1"
npm run scrape
```

Clear those variables before a full run, or open a new terminal. `MAX_PAGES` stops a ZIP early and leaves it unfinished so the next full run reads it again.

A ZIP marked `truncated` returned 300 or more rows. The site will not show the rest for that 5-mile search. Lower `gridSpacingMiles` and run again to add closer ZIP codes; already finished ZIP codes are skipped.
