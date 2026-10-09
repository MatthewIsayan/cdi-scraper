import { mkdirSync } from "node:fs";
import path from "node:path";
import type { Page } from "playwright";
import { launchBrowser } from "./browser.js";
import { loadConfig, type AppConfig } from "./config.js";
import {
  agentCount,
  markSearch,
  nextSearches,
  openDb,
  saveAgents,
  syncGrid,
  type AgentRow,
} from "./db.js";
import { writeMasterCsv } from "./export.js";
import { buildGrid } from "./grid.js";
import { queueCapRecovery, writeRecoveryReport } from './cap-recovery.js';
import { humanPause, log, randomBetween, sleep } from "./human.js";
import { advanceWithRetry, canDeferZip, isAccessBlock } from './pagination-retry.js';

type Pagination = { start: number; end: number; total: number; text: string };
type PageSnapshot = { pagination: Pagination | null; agents: AgentRow[]; noData: boolean; alert: string };

let stopping = false;

process.on("SIGINT", () => {
  if (stopping) {
    console.log("Forced exit.");
    process.exit(1);
  }
  stopping = true;
  log("Stopping after the current page is saved. Press Ctrl+C again to force quit.");
});

async function nudge(page: Page): Promise<void> {
  const x = 180 + Math.random() * 700;
  const y = 140 + Math.random() * 420;
  await page.mouse.move(x, y, { steps: 6 + Math.floor(Math.random() * 12) });
}

// These run inside the page. They are plain strings so the TypeScript loader
// cannot inject helpers that the browser does not have.
const readSnapshotFn = new Function(`
  const label = document.querySelector(".a-IRR-pagination-label")?.textContent || "";
  const match = String(label).match(/(\\d+)\\s*-\\s*(\\d+)\\s+of\\s+(\\d+)/i);
  const pagination = match ? {
    start: Number(match[1]),
    end: Number(match[2]),
    total: Number(match[3]),
    text: match[0].replace(/\\s+/g, " ").trim()
  } : null;

  const agents = Array.from(document.querySelectorAll("a"))
    .filter((anchor) => (anchor.textContent || "").includes("Check A License"))
    .map((anchor) => {
      const cell = anchor.closest("td");
      if (!cell) return null;
      const lines = (cell.querySelector("b")?.innerText || cell.innerText || "")
        .split("\\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .filter((line) => !line.includes("Check A License") && !line.includes("Get Directions"));
      const name = lines[0] || "";
      const phoneLine = lines.find((line) => /^phone:/i.test(line));
      const phone = phoneLine ? phoneLine.replace(/^phone:\\s*/i, "").trim() : "";
      const address = lines.slice(1).filter((line) => !/^phone:/i.test(line)).join(", ");
      const licenseUrl = anchor.href || "";
      let licenseNumber = "";
      let individualId = "";
      try {
        const url = new URL(licenseUrl);
        licenseNumber = url.searchParams.get("SearchLicNbr") || "";
        individualId = url.searchParams.get("SearchIndvId") || "";
      } catch (error) {
        licenseNumber = "";
      }
      const directions = Array.from(cell.querySelectorAll("a")).find((link) => (link.textContent || "").includes("Get Directions"));
      const key = licenseNumber || (individualId ? "id:" + individualId : "fallback:" + name + "|" + address + "|" + phone);
      return {
        licenseNumber: key,
        individualId,
        name,
        address,
        phone,
        licenseUrl,
        directionsUrl: directions ? directions.href : "",
        rawText: lines.join(" | ")
      };
    })
    .filter((agent) => agent && agent.name);

  const report = document.querySelector("#myreport")?.textContent || "";
  const pageText = (document.body?.innerText || "").replace(/\\s+/g, " ");
  const alert = Array.from(document.querySelectorAll(".t-Alert-content, .a-Form-error"))
    .map((node) => (node.textContent || "").trim())
    .filter(Boolean)
    .join(" ");

  const noData = agents.length === 0 && (
    /no data found/i.test(report) || /no agents were found within your search area/i.test(pageText)
  );
  return { pagination, agents, noData, alert };
`) as () => PageSnapshot;

const markWaitingFn = new Function(`document.documentElement.dataset.cdiWait = "1";`) as () => void;
const stillWaitingFn = new Function(`return document.documentElement.dataset.cdiWait === "1";`) as () => boolean;
const sessionExpiredFn = new Function(`
  const text = (document.body && document.body.innerText) || "";
  return /session has expired|session has ended|session state protection/i.test(text);
`) as () => boolean;

class SessionExpiredError extends Error {
  constructor() {
    super("The Department of Insurance session expired");
    this.name = "SessionExpiredError";
  }
}

const nextButtonStateFn = new Function(`
  const label = document.querySelector(".a-IRR-pagination-label")?.textContent || "";
  const range = label.match(/(\\d+)\\s*-\\s*(\\d+)\\s+of\\s+(\\d+)/i);
  if (range && Number(range[2]) < Number(range[3])) {
    return "ok:button[aria-label=\\"Next\\"]";
  }
  const selected = Array.from(document.querySelectorAll("#resultshub a"))
    .find((link) => (link.textContent || "").includes("✓"));
  const selectedStart = Number((selected?.textContent || "1").match(/\\d+/)?.[0] || 1);
  for (const selector of ["#thru200 span", "#thru300 span"]) {
    const link = document.querySelector(selector);
    const text = (link?.textContent || "").replace(/\\s+/g, " ").trim();
    const start = Number(text.match(/\\d+/)?.[0] || 0);
    if (link && text && start > selectedStart && !text.includes("✓")) return "ok:" + selector;
  }
  const button = Array.from(document.querySelectorAll("button")).find((candidate) => {
    return candidate.getAttribute("aria-label") === "Next" || candidate.title === "Next";
  });
  if (!button) return "missing";
  const disabled = button.disabled || button.getAttribute("aria-disabled") === "true"
    || (button.closest("li") && button.closest("li").classList.contains("is-disabled"));
  return disabled ? "disabled" : "ok:button[aria-label=\\"Next\\"]";
`) as () => string;

async function readSnapshot(page: Page): Promise<PageSnapshot> {
  return page.evaluate(readSnapshotFn);
}

async function assertSession(page: Page): Promise<void> {
  const blocked = await page.evaluate(() => /captcha|verify you are human|access denied|too many requests/i.test(document.body?.innerText || ''));
  if (blocked) throw new Error('Access denied or verification challenge; manual review required');
  const expired = await page.evaluate(sessionExpiredFn).catch(() => false);
  if (expired) throw new SessionExpiredError();
}

function isSessionError(error: unknown): boolean {
  if (error instanceof SessionExpiredError) return true;
  const message = error instanceof Error ? error.message : String(error);
  return /session has expired|session has ended|session state protection/i.test(message);
}

async function openSearch(page: Page, config: AppConfig): Promise<void> {
  await page.goto(config.startUrl, { waitUntil: "domcontentloaded" });
  await assertSession(page);
  await page.waitForSelector("#P1_INSURANCE_TYPE");
  await humanPause([800, 1600]);
}

async function typeZip(page: Page, zip: string, config: AppConfig): Promise<void> {
  const input = page.locator("#P1_ZIP_CITY_STATE");
  await input.click();
  await humanPause([200, 500]);
  await input.fill("");
  await humanPause([250, 600]);
  for (const character of zip) {
    await page.keyboard.type(character, { delay: randomBetween(config.typingDelayMs[0], config.typingDelayMs[1]) });
  }
  await humanPause([400, 900]);
}

async function clickButton(page: Page, selector: string): Promise<void> {
  const button = page.locator(selector).first();
  const box = await button.boundingBox();
  if (box) {
    await page.mouse.move(
      box.x + box.width / 2 + randomBetween(-3, 3),
      box.y + box.height / 2 + randomBetween(-2, 2),
      { steps: 10 },
    );
    await sleep(randomBetween(120, 380));
  }
  await button.click();
}

async function waitForFreshResults(page: Page): Promise<void> {
  await page.evaluate(markWaitingFn);
  await clickButton(page, "#runSearch");
  const deadline = Date.now() + 70_000;
  while (Date.now() < deadline) {
    const waiting = await page.evaluate(stillWaitingFn).catch(() => true);
    if (!waiting) break;
    await sleep(300);
  }
  if (Date.now() >= deadline) {
    throw new Error("Timed out waiting for the search to finish");
  }
  await assertSession(page);
  await page.waitForSelector("#P1_ZIP_CITY_STATE", { timeout: 30_000 });
  const settled = Date.now() + 12_000;
  let snapshot = await readSnapshot(page);
  while (!snapshot.pagination && !snapshot.noData && !snapshot.alert && Date.now() < settled) {
    await sleep(400);
    snapshot = await readSnapshot(page);
  }
  await humanPause([900, 1800]);
}

async function searchZip(page: Page, zip: string, config: AppConfig): Promise<PageSnapshot> {
  if ((await page.locator("#P1_INSURANCE_TYPE").count()) === 0) {
    await openSearch(page, config);
  }
  await nudge(page);
  await page.selectOption("#P1_INSURANCE_TYPE", config.insuranceType);
  await humanPause([350, 800]);
  await page.selectOption("#P1_LANGUAGES", config.language);
  await humanPause([350, 800]);
  await page.selectOption("#P1_DISTANCE", config.distanceValue);
  await humanPause([400, 900]);
  await typeZip(page, zip, config);
  await waitForFreshResults(page);

  await assertSession(page);
  const appliedZip = await page.locator("#P1_ZIP").inputValue().catch(() => "");
  const snapshot = await readSnapshot(page);
  if (!snapshot.pagination && !snapshot.noData) {
    const message = snapshot.alert || `Search for ${zip} did not return a result list`;
    throw new Error(message);
  }
  if (appliedZip && appliedZip !== zip) {
    throw new Error(`Site searched ${appliedZip} instead of ${zip}`);
  }
  return snapshot;
}

async function clickNext(page: Page): Promise<boolean> {
  const state = await page.evaluate(nextButtonStateFn);
  if (!state.startsWith("ok:")) return false;
  const selector = state.slice(3);

  const before = await readSnapshot(page);
  const eventName = selector.includes("thru200")
    ? "DA100TO200Event"
    : selector.includes("thru300")
      ? "DA200TO300Event"
      : null;
  const pending = new Set<import('playwright').Request>();
  let blocked = '';
  const onRequest = (request: import('playwright').Request) => {
    if (['xhr', 'fetch'].includes(request.resourceType())) pending.add(request);
  };
  const onFinished = (request: import('playwright').Request) => { pending.delete(request); };
  const onFailed = (request: import('playwright').Request) => {
    pending.delete(request);
    log(`Pagination request failed: ${request.failure()?.errorText || 'unknown error'}`);
  };
  const onResponse = (response: import('playwright').Response) => {
    if (response.status() === 403 || response.status() === 429) blocked = `HTTP ${response.status()} during pagination; manual review required`;
    if (response.status() >= 400) log(`Pagination HTTP ${response.status()}`);
  };
  const changed = async () => {
    if (blocked) throw new Error(blocked);
    await assertSession(page);
    const after = await readSnapshot(page).catch(() => null);
    if (!after?.agents.length || !after.pagination) return false;
    const pageChanged = after.pagination?.text && after.pagination.text !== before.pagination?.text;
    const agentChanged = after.agents[0]?.licenseNumber && after.agents[0].licenseNumber !== before.agents[0]?.licenseNumber;
    // Each 100-record group restarts its page numbers; verify rows changed too.
    return Boolean(agentChanged && (eventName || pageChanged));
  };
  page.on('request', onRequest);
  page.on('requestfinished', onFinished);
  page.on('requestfailed', onFailed);
  page.on('response', onResponse);
  try {
    await advanceWithRetry({
      changed,
      pending: () => pending.size > 0,
      trigger: async (attempt) => {
        log(`Pagination from ${before.pagination?.text}: ${selector}, attempt ${attempt + 1}`);
        // Use the site's actual control first, rather than synthesizing its event.
        if (attempt === 1 && eventName) {
          await page.evaluate((event) => {
            if (!(window as any).jQuery) throw new Error('Pagination event handler unavailable');
            (window as any).jQuery.event.trigger(event);
          }, eventName);
        } else await clickButton(page, selector);
      },
      wait: async (milliseconds) => {
        const deadline = Date.now() + milliseconds;
        while (Date.now() < deadline) {
          await sleep(350);
          if (await changed()) return true;
        }
        return false;
      },
      note: log,
    });
    return true;
  } finally {
    page.off('request', onRequest);
    page.off('requestfinished', onFinished);
    page.off('requestfailed', onFailed);
    page.off('response', onResponse);
  }
}

async function scrapeZip(page: Page, zip: string, config: AppConfig, db: ReturnType<typeof openDb>): Promise<void> {
  markSearch(db, zip, { status: "in_progress", error: null, pagesDone: 0, agentsSeen: 0 });
  let snapshot = await searchZip(page, zip, config);
  let pagesDone = 0;
  let agentsSeen = 0;

  if (snapshot.noData || (snapshot.pagination && snapshot.pagination.total === 0)) {
    markSearch(db, zip, { status: "complete", totalReported: 0, pagesDone: 0, agentsSeen: 0, error: null });
    log(`${zip} has no agents`);
    return;
  }

  while (!stopping) {
    if (!snapshot.agents.length || !snapshot.pagination) {
      throw new Error(`No agents found for ${zip}`);
    }
    const added = saveAgents(db, zip, snapshot.agents);
    pagesDone += 1;
    agentsSeen += snapshot.agents.length;
    markSearch(db, zip, {
      status: "in_progress",
      totalReported: snapshot.pagination.total,
      pagesDone,
      agentsSeen,
      error: null,
    });
    log(
      `${zip} | ${snapshot.pagination.text} | +${added} new | ${agentCount(db)} unique`,
    );
    try {
      writeMasterCsv(db);
    } catch (error) {
      log(`CSV update failed and will be retried on the next page: ${error instanceof Error ? error.message : String(error)}`);
    }

    const reachedTestCap = config.maxPages != null && pagesDone >= config.maxPages;
    if (reachedTestCap) {
      markSearch(db, zip, {
        status: "in_progress",
        totalReported: snapshot.pagination.total,
        pagesDone,
        agentsSeen,
        error: null,
      });
      return;
    }

    await humanPause(config.pageDelayMs);
    if (stopping) return;
    const moved = await clickNext(page);
    if (!moved) {
      const truncated = agentsSeen >= 300;
      markSearch(db, zip, {
        status: truncated ? "truncated" : "complete",
        totalReported: snapshot.pagination.total,
        pagesDone,
        agentsSeen,
        error: truncated ? "Site ended after 300 results; additional results may be unavailable" : null,
      });
      if (truncated) log(`${zip} reached the site's 300-result maximum.`);
      return;
    }
    await humanPause([700, 1400]);
    await assertSession(page);
    snapshot = await readSnapshot(page);
  }
}

async function main(): Promise<void> {
  const config = loadConfig();
  const db = openDb();
  const grid = buildGrid(config.centerZip, config.coverageMiles, config.gridSpacingMiles);
  syncGrid(db, grid);
  queueCapRecovery(db, config.centerZip, config.coverageMiles);
  const queue = nextSearches(db, config.maxZips);
  const queued = new Set(queue.map(search => search.zip));

  log(
    `Grid has ${grid.length} ZIP codes within ${config.coverageMiles} miles of ${config.centerZip}. ${queue.length} still need a search.`,
  );
  if (queue.length === 0) {
    const target = writeMasterCsv(db);
    log(`Nothing left to search. Master CSV: ${target}`);
    db.close();
    return;
  }

  mkdirSync(path.join(process.cwd(), "logs"), { recursive: true });
  const { context, page } = await launchBrowser(config);
  let giveUp = false;
  let unresolvedCaps = 0;
  let deferredZips = 0;
  try {
    await openSearch(page, config);
    let first = true;
    for (const search of queue) {
      if (stopping || giveUp) break;
      if (!first) {
        log(`Pausing before ${search.zip} so this does not look like a rapid crawl`);
        await humanPause(config.zipDelayMs);
      }
      first = false;
      if (stopping) break;

      let attempt = 0;
      while (attempt < config.maxAttempts && !stopping) {
        attempt += 1;
        try {
          log(`Searching ${search.zip} ${search.city} (${search.distance_miles.toFixed(1)} mi)${attempt > 1 ? ` attempt ${attempt}` : ""}`);
          const started = Date.now();
          try {
            await scrapeZip(page, search.zip, config, db);
          } finally {
            db.prepare('INSERT INTO search_effort(zip,seconds) VALUES(?,?) ON CONFLICT(zip) DO UPDATE SET seconds=seconds+excluded.seconds')
              .run(search.zip,(Date.now()-started)/1000);
            writeRecoveryReport(db);
          }
          const added = queueCapRecovery(db, config.centerZip, config.coverageMiles);
          writeRecoveryReport(db);
          if (added) log(`Queued ${added} nearby ZIP searches for capped areas; capped searches remain unresolved.`);
          if (config.maxZips == null) {
            for (const followup of nextSearches(db)) {
              if (!queued.has(followup.zip)) { queue.push(followup); queued.add(followup.zip); }
            }
          }
          break;
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          const sessionExpired = isSessionError(error);
          log(
            sessionExpired
              ? `Session expired on ${search.zip}. Opening a fresh search page.`
              : `Problem on ${search.zip}: ${message}`,
          );
          await page.screenshot({ path: path.join(process.cwd(), "logs", "last-error.png"), fullPage: true }).catch(() => undefined);
          markSearch(db, search.zip, { status: "error", error: message });
          if (isAccessBlock(message)) {
            giveUp = true;
            log(`Stopping for access/verification review: ${message}`);
            break;
          }
          if (attempt >= config.maxAttempts) {
            if (canDeferZip(message)) {
              deferredZips += 1;
              log(`Deferred ${search.zip} after ${config.maxAttempts} timeout attempts; saved data preserved, ZIP remains incomplete. Continuing other ZIPs.`);
              await openSearch(page, config);
              break;
            }
            giveUp = true;
            log(`Stopping. ${search.zip} failed ${config.maxAttempts} times. Saved agents are preserved.`);
            break;
          }
          await humanPause([20000, 40000]);
          await openSearch(page, config).catch(() => undefined);
        }
      }
    }
  } finally {
    try {
      const target = writeMasterCsv(db);
      log(`Master CSV updated: ${target}`);
    } catch (error) {
      log(`Final CSV export failed: ${error instanceof Error ? error.message : String(error)}`);
    }
    await context.close();
    unresolvedCaps = (db.prepare("SELECT COUNT(*) AS n FROM searches WHERE status='truncated'").get() as {n:number}).n;
    db.close();
  }
  if (giveUp) {
    log("Run npm run scrape again to continue unfinished searches.");
    process.exitCode = 1;
  } else if (stopping) {
    log("Stopped. Run the same command again and it will continue unfinished ZIP codes.");
  } else {
    log(`Finished this queue pass. ${deferredZips} ZIPs deferred for timeout recovery; ${unresolvedCaps} capped searches remain potentially incomplete.`);
    if (deferredZips) {
      log('Timed out ZIPs remain queued; requesting a supervised recovery pass.');
      process.exitCode = 1;
    }
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack : error);
  process.exit(1);
});
