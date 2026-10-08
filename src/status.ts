import { openDb, statusCounts } from "./db.js";

const db = openDb();
try {
  const status = statusCounts(db);
  console.log(`Unique agents saved: ${status.agents}`);
  if (status.byStatus.length === 0) {
    console.log("No ZIP searches queued yet. Run npm run scrape or npm run grid.");
  } else {
    for (const row of status.byStatus) {
      console.log(`${row.status.padEnd(12)} ${row.count}`);
    }
  }
  const problems = db.prepare(`
    SELECT zip, city, status, total_reported, error
    FROM searches
    WHERE status IN ('error', 'truncated', 'in_progress')
    ORDER BY status, zip
  `).all() as { zip: string; city: string; status: string; total_reported: number | null; error: string | null }[];
  for (const row of problems) {
    const reported = row.total_reported != null ? `, site reported ${row.total_reported}` : "";
    const detail = row.error ? ` — ${row.error}` : row.status === "in_progress" ? ` — not finished${reported}` : reported;
    console.log(`${row.status} ${row.zip} ${row.city}${detail}`);
  }
} finally {
  db.close();
}
