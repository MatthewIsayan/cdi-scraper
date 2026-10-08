import csv, json, re, time, urllib.request
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'exports/first-ten-test'
CACHE.mkdir(parents=True,exist_ok=True)
with (ROOT/'ROUND-1-BACKUP/cdi-agents.csv').open(encoding='utf-8-sig',newline='') as f:
    reader=csv.DictReader(f)
    rows=[]
    for i,row in enumerate(reader):
        if i==10: break
        rows.append(row)
results=[]
for i,row in enumerate(rows,1):
    error=''
    for attempt in range(3):
        try:
            req=urllib.request.Request(row['license_url'],headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=30) as response:
                doc=response.read().decode('utf-8-sig')
            if not re.search(r'License #:\s*'+re.escape(row['license_number'])+r'\s*<',doc):
                raise ValueError('License identity mismatch or unavailable record')
            (CACHE/(row['license_number']+'.html')).write_text(doc,encoding='utf-8')
            error=''
            break
        except Exception as e:
            error=str(e)
            if attempt<2:time.sleep(2)
    results.append({'input':row,'checked_at_utc':datetime.now(timezone.utc).isoformat(),'error':error})
    print(i,row['name'],'Fetched' if not error else error,flush=True)
    time.sleep(.75)
(CACHE/'source-rows.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
