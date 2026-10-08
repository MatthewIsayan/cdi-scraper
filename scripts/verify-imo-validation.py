from pathlib import Path
import json,openpyxl
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/imo-validation'
a=json.loads((OUT/'validation-data.json').read_text());facts={r['license']:r for r in a['records']}
wb=openpyxl.load_workbook(OUT/'IMO_Producer_Review.xlsx',data_only=True)
seen=[];rows=0
for sn in ['Life review','Other licenses']:
    s=wb[sn]
    for cells in s.iter_rows(min_row=6,values_only=True):
        if not cells[1]:continue
        lic=cells[1];assert lic in facts,(sn,lic);seen.append(lic);r=facts[lic]
        assert cells[0]==r['name']
        assert cells[2]==r['original'] and cells[3]==r['decision']
        assert cells[39]==r['source']
        assert cells[40]=='2026-10-08'
        assert (cells[42]or'')==r['all_qualifications']
        assert (cells[43]or'')==r['search_status']
        assert all(str(v)not in ['#REF!','#VALUE!','#NAME?','#DIV/0!','#NUM!','#N/A']for v in cells)
        rows+=1
assert rows==1705 and len(set(seen))==1705 and set(seen)==set(facts)
assert sum(r['original']=='Approved'for r in facts.values())==136
assert sum(not r['active_life'] and r['decision']=='REVIEW'for r in facts.values())==20
assert wb['Summary']['D9'].value==338
assert wb['Summary']['C6'].value==35
assert wb['Summary']['G6'].value==338 and wb['Summary']['H6'].value==1367
assert wb['Summary']['B15'].value==20
for stem,count in [('IMO_Recruiting_Analysis',10),('Reviewer_Checklist',1)]:
    reader=PdfReader(OUT/(stem+'.pdf'));assert len(reader.pages)==count
    text='\n'.join(p.extract_text()for p in reader.pages)
    if stem.startswith('IMO_'):
        for r in facts.values():
            if r['original']=='Omitted' and r['prior_tier']==1:assert r['license']in text
        assert '1,347' in text and 'Twenty detail pages' in text
print('PASS: 1,705 exact license IDs, memberships, decisions, source URLs, full qualification fields, summary caches, 20 missing-data holds, all 35 discrepancy IDs in report, and PDF page counts.')
