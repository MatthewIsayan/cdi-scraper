import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { DatabaseSync } from "node:sqlite";
import { allAgents, openDb, type CsvAgent } from "./db.js";
import { log } from "./human.js";

const columns: (keyof CsvAgent)[] = [
  "name",
  "address",
  "phone",
  "license_number",
  "individual_id",
  "license_url",
  "directions_url",
  "source_zips",
  "raw_text",
];

function escapeCell(value: string): string {
  return `"${value.replaceAll('"', '""')}"`;
}

export function writeMasterCsv(db: DatabaseSync): string {
  const rows = allAgents(db);
  const lines = [
    columns.join(","),
    ...rows.map((row) => columns.map((column) => escapeCell(row[column] ?? "")).join(",")),
  ];
  const csv = `\uFEFF${lines.join("\r\n")}\r\n`;
  const directory = path.join(process.cwd(), "exports");
  mkdirSync(directory, { recursive: true });
  const target = path.join(directory, "armenian-life-annuity-agents.csv");
  const temporary = path.join(directory, "armenian-life-annuity-agents.csv.tmp");
  writeFileSync(temporary, csv, "utf8");
  try {
    renameSync(temporary, target);
  } catch {
    writeFileSync(target, csv, "utf8");
  }
  return target;
}

const isDirectRun = process.argv[1]?.replaceAll("\\", "/").endsWith("/src/export.ts");
if (isDirectRun) {
  const db = openDb();
  try {
    const target = writeMasterCsv(db);
    const count = allAgents(db).length;
    log(`Exported ${count} unique agents to ${target}`);
  } finally {
    db.close();
  }
}
