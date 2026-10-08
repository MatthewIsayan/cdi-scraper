import { readFileSync } from "node:fs";
import path from "node:path";

export type AppConfig = {
  centerZip: string;
  coverageMiles: number;
  gridSpacingMiles: number;
  insuranceType: string;
  language: string;
  distanceValue: string;
  headless: boolean;
  pageDelayMs: [number, number];
  zipDelayMs: [number, number];
  typingDelayMs: [number, number];
  maxZips?: number;
  maxPages?: number;
  startUrl: string;
};

type FileConfig = Partial<Omit<AppConfig, "maxZips" | "maxPages" | "startUrl" | "headless">> & {
  headless?: boolean;
};

function argValue(flag: string): string | undefined {
  const index = process.argv.indexOf(flag);
  if (index === -1) return undefined;
  const value = process.argv[index + 1];
  if (!value || value.startsWith("--")) {
    throw new Error(`${flag} needs a value`);
  }
  return value;
}

function numberArg(flag: string, envName?: string): number | undefined {
  const value = argValue(flag) ?? (envName ? process.env[envName] : undefined);
  if (value === undefined || value === "") return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`${flag} must be a number`);
  return parsed;
}

function pair(value: unknown, fallback: [number, number], label: string): [number, number] {
  if (!Array.isArray(value) || value.length !== 2) return fallback;
  const min = Number(value[0]);
  const max = Number(value[1]);
  if (!Number.isFinite(min) || !Number.isFinite(max) || min < 0 || max < min) {
    throw new Error(`${label} must be [min, max] milliseconds`);
  }
  return [min, max];
}

export function loadConfig(): AppConfig {
  const filePath = path.join(process.cwd(), "config.json");
  const file = JSON.parse(readFileSync(filePath, "utf8")) as FileConfig;

  const config: AppConfig = {
    centerZip: argValue("--center") ?? file.centerZip ?? "91506",
    coverageMiles: numberArg("--coverage-miles") ?? file.coverageMiles ?? 15,
    gridSpacingMiles: numberArg("--spacing-miles") ?? file.gridSpacingMiles ?? 4,
    insuranceType: file.insuranceType ?? "LIFE_ANU",
    language: file.language ?? "ARMN",
    distanceValue: file.distanceValue ?? "8.0467",
    headless:
      process.argv.includes("--headless") || process.env.HEADLESS === "1"
        ? true
        : (file.headless ?? false),
    pageDelayMs: pair(file.pageDelayMs, [3500, 7000], "pageDelayMs"),
    zipDelayMs: pair(file.zipDelayMs, [15000, 32000], "zipDelayMs"),
    typingDelayMs: pair(file.typingDelayMs, [90, 190], "typingDelayMs"),
    maxZips: numberArg("--max-zips", "MAX_ZIPS"),
    maxPages: numberArg("--max-pages", "MAX_PAGES"),
    startUrl: "https://interactive.web.insurance.ca.gov/apex_extprd/f?p=119:1::::::",
  };

  if (!/^\d{5}$/.test(config.centerZip)) {
    throw new Error(`centerZip must be 5 digits, got ${config.centerZip}`);
  }
  if (config.coverageMiles <= 0 || config.coverageMiles > 100) {
    throw new Error("coverageMiles must be between 1 and 100");
  }
  if (config.gridSpacingMiles < 0 || config.gridSpacingMiles > 20) {
    throw new Error("gridSpacingMiles must be between 0 and 20");
  }
  return config;
}
