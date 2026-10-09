import { mkdirSync } from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import type { GridPoint } from "./grid.js";

export type AgentRow = {
  licenseNumber: string;
  individualId: string;
  name: string;
  address: string;
  phone: string;
  licenseUrl: string;
  directionsUrl: string;
  rawText: string;
};

export type SearchRow = {
  zip: string;
  city: string;
  latitude: number;
  longitude: number;
  distance_miles: number;
  status: string;
  total_reported: number | null;
  pages_done: number;
  agents_seen: number;
  error: string | null;
};

const dbPath = path.join(process.cwd(), "data", "agents.db");

export function openDb(): DatabaseSync {
  mkdirSync(path.dirname(dbPath), { recursive: true });
  const db = new DatabaseSync(dbPath);
  db.exec(`
    PRAGMA journal_mode = WAL;
    PRAGMA busy_timeout = 8000;
    CREATE TABLE IF NOT EXISTS searches (
      zip TEXT PRIMARY KEY,
      city TEXT,
      latitude REAL,
      longitude REAL,
      distance_miles REAL,
      status TEXT NOT NULL,
      total_reported INTEGER,
      pages_done INTEGER NOT NULL DEFAULT 0,
      agents_seen INTEGER NOT NULL DEFAULT 0,
      error TEXT,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS agents (
      license_number TEXT PRIMARY KEY,
      individual_id TEXT,
      name TEXT NOT NULL,
      address TEXT,
      phone TEXT,
      license_url TEXT,
      directions_url TEXT,
      raw_text TEXT,
      first_zip TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS agent_zips (
      license_number TEXT NOT NULL,
      zip TEXT NOT NULL,
      PRIMARY KEY (license_number, zip)
    );
  `);
  return db;
}

function now(): string {
  return new Date().toISOString();
}

export function syncGrid(db: DatabaseSync, points: GridPoint[]): void {
  const upsert = db.prepare(`
    INSERT INTO searches (
      zip, city, latitude, longitude, distance_miles, status, updated_at
    ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
    ON CONFLICT(zip) DO UPDATE SET
      city = excluded.city,
      latitude = excluded.latitude,
      longitude = excluded.longitude,
      distance_miles = excluded.distance_miles
  `);
  const keep = new Set(points.map((point) => point.zip));
  const removePending = db.prepare(`DELETE FROM searches WHERE zip = ? AND status = 'pending'`);

  db.exec("BEGIN");
  try {
    for (const point of points) {
      upsert.run(point.zip, point.city, point.latitude, point.longitude, point.distanceMiles, now());
    }
    const pending = db.prepare(`SELECT zip FROM searches WHERE status = 'pending'`).all() as { zip: string }[];
    for (const row of pending) {
      if (!keep.has(row.zip)) removePending.run(row.zip);
    }
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

export function nextSearches(db: DatabaseSync, limit?: number): SearchRow[] {
  const sql = `
    SELECT zip, city, latitude, longitude, distance_miles, status,
           total_reported, pages_done, agents_seen, error
    FROM searches
    WHERE status IN ('pending', 'in_progress', 'error')
    ORDER BY
      CASE status WHEN 'in_progress' THEN 0 WHEN 'error' THEN 1 ELSE 2 END,
      distance_miles ASC,
      zip ASC
    ${limit ? "LIMIT ?" : ""}
  `;
  const statement = db.prepare(sql);
  return (limit ? statement.all(limit) : statement.all()) as SearchRow[];
}

export function markSearch(
  db: DatabaseSync,
  zip: string,
  patch: {
    status: string;
    totalReported?: number | null;
    pagesDone?: number;
    agentsSeen?: number;
    error?: string | null;
  },
): void {
  db.prepare(`
    UPDATE searches SET
      status = ?,
      total_reported = COALESCE(?, total_reported),
      pages_done = COALESCE(?, pages_done),
      agents_seen = COALESCE(?, agents_seen),
      error = ?,
      updated_at = ?
    WHERE zip = ?
  `).run(
    patch.status,
    patch.totalReported ?? null,
    patch.pagesDone ?? null,
    patch.agentsSeen ?? null,
    patch.error ?? null,
    now(),
    zip,
  );
}

export function saveAgents(db: DatabaseSync, zip: string, agents: AgentRow[]): number {
  const insertAgent = db.prepare(`
    INSERT INTO agents (
      license_number, individual_id, name, address, phone,
      license_url, directions_url, raw_text, first_zip, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(license_number) DO UPDATE SET
      individual_id = excluded.individual_id,
      name = excluded.name,
      address = excluded.address,
      phone = excluded.phone,
      license_url = excluded.license_url,
      directions_url = excluded.directions_url,
      raw_text = excluded.raw_text,
      updated_at = excluded.updated_at
  `);
  const link = db.prepare(`
    INSERT INTO agent_zips (license_number, zip) VALUES (?, ?)
    ON CONFLICT(license_number, zip) DO NOTHING
  `);
  const existed = db.prepare(`SELECT 1 FROM agents WHERE license_number = ?`);

  let added = 0;
  const stamp = now();
  db.exec("BEGIN");
  try {
    for (const agent of agents) {
      const isNew = !existed.get(agent.licenseNumber);
      insertAgent.run(
        agent.licenseNumber,
        agent.individualId,
        agent.name,
        agent.address,
        agent.phone,
        agent.licenseUrl,
        agent.directionsUrl,
        agent.rawText,
        zip,
        stamp,
        stamp,
      );
      link.run(agent.licenseNumber, zip);
      if (isNew) added += 1;
    }
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
  return added;
}

export function agentCount(db: DatabaseSync): number {
  const row = db.prepare(`SELECT COUNT(*) AS count FROM agents`).get() as { count: number };
  return row.count;
}

export type StatusCounts = {
  agents: number;
  byStatus: { status: string; count: number }[];
};

export function statusCounts(db: DatabaseSync): StatusCounts {
  return {
    agents: agentCount(db),
    byStatus: db.prepare(`
      SELECT status, COUNT(*) AS count
      FROM searches
      GROUP BY status
      ORDER BY status
    `).all() as { status: string; count: number }[],
  };
}

export type CsvAgent = {
  name: string;
  address: string;
  phone: string;
  license_number: string;
  individual_id: string;
  license_url: string;
  directions_url: string;
  source_zips: string;
  raw_text: string;
};

export function allAgents(db: DatabaseSync): CsvAgent[] {
  return db.prepare(`
    SELECT
      a.name,
      a.address,
      a.phone,
      a.license_number,
      COALESCE(a.individual_id, '') AS individual_id,
      COALESCE(a.license_url, '') AS license_url,
      COALESCE(a.directions_url, '') AS directions_url,
      COALESCE((
        SELECT group_concat(z.zip, ' ')
        FROM agent_zips z
        WHERE z.license_number = a.license_number
      ), '') AS source_zips,
      COALESCE(a.raw_text, '') AS raw_text
    FROM agents a
    ORDER BY a.name COLLATE NOCASE, a.license_number
  `).all() as CsvAgent[];
}
