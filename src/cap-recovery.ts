import type { DatabaseSync } from 'node:sqlite';
import { buildGrid, milesBetween, type GridPoint } from './grid.js';
import { mkdirSync, writeFileSync } from 'node:fs';

// Extra search centers improve overlap; they cannot prove recovery of all hidden records.
export const RECOVERY_LIMITS = { perZip: 8, depth: 2, additionalZips: 200 };
export type RecoveryYield = { child_zip: string; status: string; records: number; new_agents: number; seconds: number };
export function worthwhile(row: RecoveryYield): boolean {
  return row.new_agents >= 10 || (row.records > 0 && row.new_agents / row.records >= 0.05);
}
export function recoveryYield(db: DatabaseSync, parent: string): RecoveryYield[] {
  return db.prepare(`SELECT r.child_zip,s.status,
    (SELECT COUNT(*) FROM agent_zips z WHERE z.zip=r.child_zip) AS records,
    (SELECT COUNT(*) FROM agents a WHERE a.first_zip=r.child_zip) AS new_agents,
    COALESCE((SELECT seconds FROM search_effort e WHERE e.zip=r.child_zip),0) AS seconds
    FROM cap_recovery r JOIN searches s ON s.zip=r.child_zip
    WHERE r.parent_zip=? ORDER BY r.created_at,r.child_zip`).all(parent) as RecoveryYield[];
}
export function nextRecoveryBatch(rows: RecoveryYield[]): number {
  if (!rows.length) return 2;
  if (rows.some(row => !['complete','truncated'].includes(row.status))) return 0;
  if (rows.length >= RECOVERY_LIMITS.perZip) return 0;
  if (rows.length === 1) return worthwhile(rows[0]) ? 1 : 0;
  return rows.slice(-2).some(worthwhile) ? 1 : 0;
}

export function writeRecoveryReport(db: DatabaseSync): void {
  const rows = db.prepare('SELECT DISTINCT parent_zip FROM cap_recovery ORDER BY parent_zip').all() as {parent_zip:string}[];
  const lines = ['parent_zip,followup_zip,status,records,new_agents,duplicate_percent,elapsed_seconds'];
  for (const {parent_zip} of rows) for (const row of recoveryYield(db,parent_zip)) {
    lines.push([parent_zip,row.child_zip,row.status,row.records,row.new_agents,
      row.records ? (100*(1-row.new_agents/row.records)).toFixed(1) : '',row.seconds.toFixed(1)].join(','));
  }
  mkdirSync('exports',{recursive:true});
  writeFileSync('exports/cap-recovery.csv',lines.join('\n')+'\n');
}

export function recoveryCandidates(parent: GridPoint, candidates: GridPoint[], known: Set<string>): GridPoint[] {
  const selected: GridPoint[] = [];
  const nearby = candidates.filter(p => !known.has(p.zip) && milesBetween(parent, p) >= 0.75 && milesBetween(parent, p) <= 5)
    .sort((a,b) => Math.abs(milesBetween(parent,a)-3) - Math.abs(milesBetween(parent,b)-3) || a.zip.localeCompare(b.zip));
  for (const candidate of nearby) {
    if (selected.every(p => milesBetween(p,candidate) >= 1.5)) selected.push(candidate);
    if (selected.length >= RECOVERY_LIMITS.perZip) break;
  }
  return selected;
}

export function queueCapRecovery(db: DatabaseSync, centerZip: string, coverageMiles: number): number {
  const candidates = buildGrid(centerZip, coverageMiles, 0);
  const known = new Set((db.prepare('SELECT zip FROM searches').all() as {zip:string}[]).map(p=>p.zip));
  let added = 0;
  db.exec('BEGIN');
  try {
    let extra = Number((db.prepare('SELECT COUNT(DISTINCT child_zip) AS n FROM cap_recovery').get() as {n:number}).n);
    const capped = db.prepare(`SELECT zip, city, latitude, longitude, distance_miles FROM searches WHERE status='truncated' ORDER BY distance_miles,zip`).all() as {zip:string;city:string;latitude:number;longitude:number;distance_miles:number}[];
    for (const row of capped) {
      const history = recoveryYield(db,row.zip);
      const batch = nextRecoveryBatch(history);
      if (!batch) continue;
      const source = db.prepare('SELECT MIN(depth) AS depth FROM cap_recovery WHERE child_zip=?').get(row.zip) as {depth:number|null};
      const depth = (source.depth ?? 0) + 1;
      if (depth > RECOVERY_LIMITS.depth || extra >= RECOVERY_LIMITS.additionalZips) continue;
      // A capped follow-up expands recursively only if it produced worthwhile new data.
      if (source.depth != null) {
        const own = db.prepare('SELECT parent_zip FROM cap_recovery WHERE child_zip=? LIMIT 1').get(row.zip) as {parent_zip:string};
        if (!recoveryYield(db,own.parent_zip).some(r => r.child_zip===row.zip && worthwhile(r))) continue;
      }
      const parent = {...row,distanceMiles:row.distance_miles};
      const previous = db.prepare('SELECT latitude,longitude FROM searches WHERE zip IN (SELECT child_zip FROM cap_recovery WHERE parent_zip=?)').all(row.zip) as {latitude:number;longitude:number}[];
      const options = recoveryCandidates(parent,candidates,known).filter(p=>previous.every(q=>milesBetween(p,q)>=1.5));
      const selected: GridPoint[] = [];
      if (options.length) selected.push(options.shift()!);
      // The initial pair should search different sides rather than adjacent centers.
      if (batch===2 && options.length) {
        options.sort((a,b)=>milesBetween(b,selected[0])-milesBetween(a,selected[0]));
        selected.push(options[0]);
      }
      for (const child of selected) {
        if (extra >= RECOVERY_LIMITS.additionalZips) break;
        db.prepare(`INSERT INTO searches(zip,city,latitude,longitude,distance_miles,status,updated_at) VALUES(?,?,?,?,?,'pending',?)`)
          .run(child.zip,child.city,child.latitude,child.longitude,child.distanceMiles,new Date().toISOString());
        db.prepare('INSERT INTO cap_recovery VALUES(?,?,?,?)').run(row.zip,child.zip,depth,new Date().toISOString());
        known.add(child.zip); extra++; added++;
      }
    }
    db.exec('COMMIT');
  } catch(error) { db.exec('ROLLBACK'); throw error; }
  return added;
}
