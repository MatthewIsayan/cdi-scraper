import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with (ROOT/'ROUND-1-BACKUP/cdi-agents.csv').open(encoding='utf-8-sig',newline='') as f:original=list(csv.DictReader(f))
enriched=json.loads((ROOT/'exports/first-ten-test/enriched-rows.json').read_text())
rationale={
 '0D84696':'Eligible Primerica producer with active Life and no excluded relationships.',
 '0I83730':'Eligible WFG producer with active Life and no excluded relationships.',
 '0H69689':'Active Life with no listed relationships; eligible at lower priority.',
 '0C59544':'Active Life with multiple Life insurers; mixed P&C is acceptable and Foremost alone is not excluded.',
 '0C87723':'Active Life with accepted New York Life/NYLIFE relationships; no excluded relationship found.',
 '0K82713':'Active Life with American National; additional health relationships are acceptable.',
 '0F40155':'Active Life with multiple Life insurers; USI and mixed P&C relationships are eligible.',
 '0C00443':'Excluded because current Farmers Insurance Exchange and Farmers New World Life appointments are listed.',
 '0C11447':'Active Life with multiple Life/annuity insurers and no excluded relationships.',
 '0811535':'Active Life with multiple Life insurers and no excluded relationships.',
}
rows=[]
for i,source in enumerate(original):
 r={
   'Name':source['name'],'License_Number':source['license_number'],
   'Business_Address':source['address'],'Business_Phone':source['phone'],
   'Languages':'','Active_Qualifications':'','Life_Issue_Date':'','Years_Since_Life_Issue':'',
   'Life_Expiration_Date':'','Appointed_Companies':'','Agencies':'','Recruiting_Priority':'',
   'Contact_Status':'','Checked_On':'','Rationale':'','License_URL':source['license_url'],'Passed_Test':''
 }
 if i<10:
  e=enriched[i];assert e['license_number']==source['license_number']
  for key,field in {
   'Business_Address':'Current_Business_Address','Business_Phone':'Current_Business_Phone',
   'Languages':'Reported_Languages','Active_Qualifications':'Active_Qualifications',
   'Life_Issue_Date':'Life_Issue_Date','Years_Since_Life_Issue':'Years_Since_Life_Issue',
   'Life_Expiration_Date':'Life_Expiration_Date','Appointed_Companies':'Appointed_Insurers',
   'Agencies':'Agency_Organizations','Recruiting_Priority':'Recruiting_Priority',
   'Checked_On':'Checked_On_CA','Passed_Test':'Passed_Test'
  }.items():r[key]=e[field]
  r['Contact_Status']='Do not contact - excluded' if e['Passed_Test']=='No' else 'Find contact' if not e['Current_Business_Phone'] else 'Verify direct number'
  r['Rationale']=rationale[source['license_number']]
 rows.append(r)
assert list(rows[0])[-3:]==['Rationale','License_URL','Passed_Test']
assert all(r['Passed_Test']=='' for r in rows[10:])
(ROOT/'exports/first-ten-test/compact-rows.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps({'rows':len(rows),'columns':len(rows[0]),'enriched':10,'not_evaluated':len(rows)-10}))
