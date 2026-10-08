import { mkdirSync } from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import type { BrowserContext, Page } from "playwright";
import type { AppConfig } from "./config.js";
import { log } from "./human.js";

const require = createRequire(import.meta.url);

type ChromiumExtra = {
  use: (plugin: unknown) => void;
  launchPersistentContext: (
    userDataDir: string,
    options: Record<string, unknown>,
  ) => Promise<BrowserContext>;
};

export async function launchBrowser(config: AppConfig): Promise<{ context: BrowserContext; page: Page }> {
  const { chromium } = require("playwright-extra") as { chromium: ChromiumExtra };
  const stealth = require("puppeteer-extra-plugin-stealth");
  const plugin = typeof stealth === "function" ? stealth() : stealth.default();
  chromium.use(plugin);

  const profile = path.join(process.cwd(), ".browser-profile");
  mkdirSync(profile, { recursive: true });

  const options = {
    headless: config.headless,
    viewport: { width: 1440, height: 900 },
    locale: "en-US",
    timezoneId: "America/Los_Angeles",
    ignoreDefaultArgs: ["--enable-automation"],
    args: ["--disable-blink-features=AutomationControlled"],
  };

  let context: BrowserContext;
  try {
    context = await chromium.launchPersistentContext(profile, { ...options, channel: "chrome" });
    log("Opened installed Chrome with a saved local profile");
  } catch (error) {
    log(`Installed Chrome was not usable (${error instanceof Error ? error.message : String(error)}). Opening Playwright Chromium.`);
    context = await chromium.launchPersistentContext(profile, options);
  }

  await context.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => undefined });
  });

  const page = context.pages()[0] ?? (await context.newPage());
  page.setDefaultTimeout(60_000);
  page.on("dialog", async (dialog) => {
    log(`Site dialog: ${dialog.message()}`);
    await dialog.accept();
  });
  return { context, page };
}
