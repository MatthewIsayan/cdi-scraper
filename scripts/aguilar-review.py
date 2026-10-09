"""Cache and compare public CDI records with the supplied approved directory."""
import csv
import html
import json
import re
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

ROOT = Path(__file__).resolve().parents[1] / 'exports' / 'aguilar-review'
CACHE = ROOT / 'details'
CACHE.mkdir(exist_ok=True)

def text(s):
    s = re.sub(r'<script\b.*?</script>|<style\b.*?</style>', '', s, flags=re.S|re.I)
    return ' '.join(html.unescape(re.sub('<[^>]*>', ' ', s)).split())

def table(doc, name):
    m = re.search(r'<table\b[^>]*\bid="'+name+r'"[^>]*>(.*?)</table>', doc, re.S|re.I)
    if not m: return []
    return [[text(c) for c in re.findall(r'<td\b[^>]*>(.*?)(?=</td>|<td\b|</tr>)', r, re.S|re.I)] for r in re.findall(r'<tr\b[^>]*>(.*?)</tr>', m[1], re.S|re.I) if re.search('<td\\b', r, re.I)]

approved = {r['license_number']:r for r in json.loads((ROOT/'approved.json').read_text())}
snapshot = json.loads((ROOT/'search-rows.json').read_text())
matches = {}
for r in snapshot['rows']:
    ids = re.findall(r"'([^']*)'", r['action'])
    lic, _, ind, typ = ids
    cells = r['cells']
    url = 'https://cdicloud.insurance.ca.gov/cal/LicenseDetail?' + urllib.parse.urlencode({'SearchType':typ,'SearchLicNbr':lic,'SearchIndvId':ind})
    entry = matches.setdefault(lic, {'license_number':lic,'url':url,'search_names':[], 'in_current_search':True})
    name = ' '.join(cells[:3])
    if name not in entry['search_names']: entry['search_names'].append(name)
    entry['search_status'] = cells[4] if len(cells)>4 else ''
    entry['search_city'] = cells[5] if len(cells)>5 else ''
    entry['search_state'] = cells[6] if len(cells)>6 else ''
    entry['residency'] = cells[7] if len(cells)>7 else ''
for lic,r in approved.items():
    matches.setdefault(lic, {'license_number':lic,'url':'https://cdicloud.insurance.ca.gov/cal/LicenseDetail?'+urllib.parse.urlencode({'SearchType':'IND','SearchLicNbr':lic,'SearchIndvId':lic}),'search_names':[], 'in_current_search':False})

def fetch(entry):
    lic=entry['license_number']; path=CACHE/(lic+'.html')
    try:
        if not path.exists():
            doc=urllib.request.urlopen(entry['url'],timeout=30).read().decode('utf-8-sig')
            if not re.search(r'License #:\s*'+re.escape(lic)+r'\s*<',doc): raise ValueError('license identity mismatch or unavailable')
            path.write_text(doc,encoding='utf-8')
        return lic,None
    except Exception as e: return lic,str(e)

errors={}
if '--cached-only' not in sys.argv:
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs=[pool.submit(fetch,e) for e in matches.values()]
        for i,f in enumerate(as_completed(jobs),1):
            lic,error=f.result()
            if error: errors[lic]=error
            if i%50==0 or i==len(jobs):print(f'{i}/{len(jobs)} records fetched; {len(errors)} errors',flush=True)

results=[]
for lic,e in matches.items():
    result={**e,'approved':lic in approved,**approved.get(lic,{})}
    path=CACHE/(lic+'.html')
    if not path.exists(): result['error']=errors.get(lic,'Unavailable');results.append(result);continue
    doc=path.read_text(encoding='utf-8'); flat=text(doc)
    result['qualifications']=[dict(zip(['qualification','issued','status','status_date','expires'],r)) for r in table(doc,'licenseDetailGrid')]
    result['agencies']=[r for r in table(doc,'EndorsingOrganizationsGrid')]
    result['appointments']=[r for r in table(doc,'AppointmentGrid')]
    result['enforcement']=table(doc,'EnforcementActionGrid')
    result['complaints']=table(doc,'ConsumerComplaintGrid')
    result['active_life']=any(q.get('qualification')=='Life' and q.get('status')=='Active' for q in result['qualifications'])
    m=re.search(r'Name:\s*(.*?)\s*License #:',flat);result['current_name']=m[1] if m else ''
    for field,label,end in [('business_phone','Business Phone:','Language:'),('languages','Language:','Agents:')]:
        m=re.search(re.escape(label)+r'\s*(.*?)\s*'+re.escape(end),flat);result[field]=m[1] if m else ''
    m=re.search(r'Business Address:\s*(.*?)</div>',doc,re.S|re.I)
    result['business_address']=text(m[1]) if m else ''
    results.append(result)
(ROOT/'comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
fields=['approved','license_number','current_name','in_current_search','residency','search_city','search_state','search_status','active_life','business_phone','business_address','pdf_group','qualification_summary','agencies','appointments','url','error']
with (ROOT/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for r in sorted(results,key=lambda r:(not r['approved'],r.get('current_name',''),r['license_number'])):
        row={k:r.get(k,'') for k in fields}
        row['qualification_summary']='; '.join(q['qualification']+': '+q['status'] for q in r.get('qualifications',[]))
        row['agencies']=' | '.join(' / '.join(a) for a in r.get('agencies',[]))
        row['appointments']=' | '.join(' / '.join(a) for a in r.get('appointments',[]))
        w.writerow(row)
print(json.dumps({'unique_records':len(results),'approved':sum(r['approved'] for r in results),'unlisted':sum(not r['approved'] for r in results),'errors':errors,'initials_collected':[r['initial'] for r in snapshot['searchCounts']]},indent=2),flush=True)
