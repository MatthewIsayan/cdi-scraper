import csv,json
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
source=read(ROOT/'ROUND-1-BACKUP/cdi-agents.csv')
screen=read(ROOT/'output/csv/cdi-agents-simplified-first-60-enriched.csv')
facts={e['input']['license_number']:e['facts'] for cache in ['first-ten-test','next-fifty-test'] for e in json.loads((ROOT/f'exports/{cache}/facts.json').read_text())}
def uniq(xs):return list(dict.fromkeys(xs))
def names(rs):return '; '.join(uniq(r[0] for r in rs))
def iso(s):return datetime.strptime(s,'%m/%d/%Y').date().isoformat() if s else ''
def details(rs):return ' | '.join(f'{r[0]} — {r[1]} — {iso(r[2])}' for r in rs)
rows=[]
for i,(s,t) in enumerate(zip(source,screen)):
    assert s['license_number']==t['License_Number']
    r={
      'Name':t['Name'],'Passed_Test':t['Passed_Test'],'Assessment':t['Rationale'],'License_URL':t['License_URL'],
      'License_Number':t['License_Number'],'Business_Address':t['Business_Address'],'Business_Phone':t['Business_Phone'],
      'Directions_URL':s['directions_url'],'Source_ZIPs':s['source_zips'],'Checked_On':t['Checked_On'],
      'Languages':t['Languages'],'Active_Qualifications':t['Active_Qualifications'],'Qualification_Details':'',
      'Life_Issue_Date':t['Life_Issue_Date'],'Years_Since_Life_Issue':t['Years_Since_Life_Issue'],
      'Active_Health_Authority':'','Active_PC_Authority':'','Active_Variable_Authority':'',
      'Appointed_Insurers':'','Appointment_Row_Count':'','Unique_Insurer_Count':'',
      'Life_Appointed_Insurers':'','Unique_Life_Insurer_Count':'','Health_Appointed_Insurers':'','PC_Appointed_Insurers':'','Appointment_Details':'',
      'Agency_Organizations':'','Unique_Agency_Count':'','Agency_Relationship_Count':'','Life_Agency_Organizations':'','Agency_Relationship_Details':'',
      'Latest_Displayed_Relationship_Date':'','Rule_Document':''
    }
    if i<60:
        f=facts[r['License_Number']];a=f['appointments'];g=f['agencies'];active=[q for q in f['qualifications'] if q[2]=='Active'];an=[q[0] for q in active]
        life=[x for x in a if x[1]=='Life'];health=[x for x in a if 'Health' in x[1]];pc=[x for x in a if x[1] in ['Property','Casualty','Personal Lines']]
        dates=[datetime.strptime(x[2],'%m/%d/%Y').date() for x in a+g if x[2]]
        r.update({
          'Qualification_Details':' | '.join(q[0]+' — issued '+iso(q[1]) for q in active),
          'Active_Health_Authority':'Yes' if any('Health' in q for q in an) else 'No',
          'Active_PC_Authority':'Yes' if any(q in ['Property','Casualty','Personal Lines'] for q in an) else 'No',
          'Active_Variable_Authority':'Yes' if any('Var Life' in q for q in an) else 'No',
          'Appointed_Insurers':names(a),'Appointment_Row_Count':len(a),'Unique_Insurer_Count':len(uniq(x[0] for x in a)),
          'Life_Appointed_Insurers':names(life),'Unique_Life_Insurer_Count':len(uniq(x[0] for x in life)),
          'Health_Appointed_Insurers':names(health),'PC_Appointed_Insurers':names(pc),'Appointment_Details':details(a),
          'Agency_Organizations':names(g),'Unique_Agency_Count':len(uniq(x[0] for x in g)),
          'Agency_Relationship_Count':len(g),'Life_Agency_Organizations':names([x for x in g if x[1]=='Life']),
          'Agency_Relationship_Details':details(g),'Latest_Displayed_Relationship_Date':max(dates).isoformat() if dates else '',
          'Rule_Document':'imo-final-approval-rules.md (2026-10-08)'
        })
    rows.append(r)
(ROOT/'exports/next-fifty-test/selected-rows.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps({'rows':len(rows),'columns':len(rows[0]),'first_columns':list(rows[0])[:4]}))
