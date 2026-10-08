import { createRequire } from "node:module";
import { loadConfig } from "./config.js";

const require = createRequire(import.meta.url);

type ZipLookup = {
  zip: string;
  latitude: number;
  longitude: number;
  city: string;
  state: string;
};

type Zipcodes = {
  radius: (zip: string, miles: number) => string[];
  lookup: (zip: string) => ZipLookup | undefined;
};

const zipcodes = require("zipcodes") as Zipcodes;

export type GridPoint = {
  zip: string;
  city: string;
  latitude: number;
  longitude: number;
  distanceMiles: number;
};

export function milesBetween(
  a: { latitude: number; longitude: number },
  b: { latitude: number; longitude: number },
): number {
  const earth = 3958.8;
  const dLat = ((b.latitude - a.latitude) * Math.PI) / 180;
  const dLon = ((b.longitude - a.longitude) * Math.PI) / 180;
  const lat1 = (a.latitude * Math.PI) / 180;
  const lat2 = (b.latitude * Math.PI) / 180;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * earth * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function buildGrid(centerZip: string, coverageMiles: number, spacingMiles: number): GridPoint[] {
  const center = zipcodes.lookup(centerZip);
  if (!center) throw new Error(`Unknown ZIP code ${centerZip}`);

  const nearby = zipcodes.radius(centerZip, coverageMiles + 2);
  const candidates: GridPoint[] = [];
  const seen = new Set<string>();

  for (const zip of [centerZip, ...nearby]) {
    if (seen.has(zip)) continue;
    seen.add(zip);
    const row = zipcodes.lookup(zip);
    if (!row || row.state !== "CA") continue;
    const distanceMiles = milesBetween(center, row);
    if (distanceMiles > coverageMiles + 0.05) continue;
    candidates.push({
      zip: row.zip,
      city: row.city,
      latitude: row.latitude,
      longitude: row.longitude,
      distanceMiles,
    });
  }

  candidates.sort((a, b) => a.distanceMiles - b.distanceMiles || a.zip.localeCompare(b.zip));

  if (spacingMiles <= 0) return candidates;

  const selected: GridPoint[] = [];
  for (const candidate of candidates) {
    const tooClose = selected.some(
      (point) => milesBetween(point, candidate) < spacingMiles,
    );
    if (!tooClose) selected.push(candidate);
  }
  return selected;
}

const isDirectRun = process.argv[1]?.replaceAll("\\", "/").endsWith("/src/grid.ts");
if (isDirectRun) {
  const config = loadConfig();
  const grid = buildGrid(config.centerZip, config.coverageMiles, config.gridSpacingMiles);
  console.log(
    `${grid.length} ZIP searches within ${config.coverageMiles} miles of ${config.centerZip}, spaced about ${config.gridSpacingMiles} miles apart`,
  );
  for (const point of grid) {
    console.log(
      `${point.zip}  ${point.city.padEnd(22)}  ${point.distanceMiles.toFixed(1)} mi`,
    );
  }
}
