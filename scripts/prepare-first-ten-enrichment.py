import json,re
from pathlib import Path
from datetime import datetime,date,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'exports/first-ten-test'
data=json.loads((CACHE/'facts.json').read_text())
notes={
'0D84696':('Higher','Active Life with Primerica and multiple Life insurers, including American General and Nationwide. No excluded current relationship displayed. Missing phone affects contact readiness only.'),
'0I83730':('Higher','Active Life with a WFG Life agency relationship. No insurer appointments displayed is not a rejection. The recent displayed Life issue date is not proof of beginner status.'),
'0H69689':('Lower','Active Life with no agency or insurer relationships displayed. This is eligible at lower priority under the finalized rules. No phone is displayed.'),
'0C59544':('Higher','Active Life with Protective, Pruco, Guardian and other Life appointments. P&C and health relationships are acceptable. Foremost alone does not trigger Farmers exclusion. No direct Allstate entry is displayed; do not extend bans by affiliate ownership.'),
'0C87723':('Higher','Active Life with New York Life and NYLIFE appointments, which are explicitly acceptable. Experience Insurance Services includes a Life agency entry. P&C and health-exchange relationships do not disqualify. Do not expand Allstate exclusions solely by ownership of other insurer names.'),
'0K82713':('Higher','Active Life with American National Life appointment plus health-oriented insurers and the health exchange. Mixed Life/health relationships are eligible. No excluded current relationship displayed.'),
'0F40155':('Higher','Active Life with Banner, Pacific Life, Protective and other Life appointments. USI is an insurance brokerage, not an excluded named company. P&C and inactive variable authority do not disqualify active Life.'),
'0C00443':('Not eligible','Current FARMERS INSURANCE EXCHANGE and FARMERS NEW WORLD LIFE INSURANCE COMPANY appointments trigger the Farmers exclusion. Other insurers, active Life and the producer\'s own agency do not override it.'),
'0C11447':('Higher','Active Life with American Equity, Athene, EquiTrust, Southwest and other Life appointments, plus an NDK Life agency entry. No excluded current relationship displayed. Active variable authority is acceptable.'),
'0811535':('Higher','Active Life with American General, Ameritas, Guardian, Protective and other Life appointments. Health relationships are acceptable. No excluded current relationship displayed. Missing phone affects contact readiness only.'),
}
def uniq(xs):return list(dict.fromkeys(xs))
def iso(s):
    return datetime.strptime(s,'%m/%d/%Y').date().isoformat() if s else ''
def joined(rows):return ' | '.join(' / '.join(r) for r in rows)
def years(s,asof):return round((asof-datetime.strptime(s,'%m/%d/%Y').date()).days/365.2425,2) if s else ''
enriched=[]
for i,x in enumerate(data,1):
    assert not x['error'],x['error']
    row=dict(x['input']);f=x['facts'];lic=row['license_number'];q=f['qualifications'];a=f['appointments'];g=f['agencies']
    checked=datetime.fromisoformat(x['checked_at_utc']);asof=checked.astimezone(timezone(timedelta(hours=-7))).date()
    life=next(r for r in q if r[0]=='Life')
    active=[r[0] for r in q if r[2]=='Active'];inactive=[r[0] for r in q if r[2]!='Active']
    names=uniq(r[0] for r in a);lnames=uniq(r[0] for r in a if r[1]=='Life');gnames=uniq(r[0] for r in g);lg=uniq(r[0] for r in g if r[1]=='Life')
    matches=[r for r in a+g if re.search(r'\bSTATE FARM\b|\bFARMERS\b|\bALLSTATE\b|\bKNIGHTS OF COLUMBUS\b|\bTHRIVENT\b',r[0],re.I)]
    priority,assessment=notes[lic];passed=life[2]=='Active' and not matches
    phone=f['business_phone'];tollfree=bool(re.match(r'^(?:\+?1[- .]?)?(?:800|888|877|866|855|844|833|822)[- .]',phone))
    issued=min((r[1] for r in q if r[1]),key=lambda s:datetime.strptime(s,'%m/%d/%Y'))
    last=max((r[2] for r in a+g if len(r)>2 and r[2]),key=lambda s:datetime.strptime(s,'%m/%d/%Y'),default='')
    languages=uniq(s.strip() for s in f['languages'].split(',') if s.strip())
    allrels=a+g
    flags=[]
    if not phone:flags.append('No current business phone displayed')
    else:flags.append('Listed business phone has not been verified as direct to producer')
    if not a and not g:flags.append('No agency/insurer relationship displayed; sales activity unknown')
    if f['business_address']!=row['address']:flags.append('Current address formatting/detail differs from original CSV; both preserved')
    if inactive:flags.append('Other inactive qualifications: '+', '.join(inactive))
    if matches:flags.append('Excluded current relationship overrides acceptable relationships')
    if not passed:contact='NOT FOR OUTREACH - FAIL'
    elif not phone:contact='SAVE - NEEDS CONTACT'
    elif tollfree:contact='SAVE - NEEDS DIRECT CONTACT'
    else:contact='SAVE - VERIFY DIRECT CONTACT'
    agency_sources='https://www.usi.com/' if any('USI INSURANCE' in n for n in gnames) else ''
    added={
      'Input_Row_Number':i,'Checked_At_UTC':x['checked_at_utc'],'Checked_On_CA':asof.isoformat(),
      'Source_Record_Status':'Retrieved and license number verified','Current_License_Name':f['name'],
      'Active_Qualifications':'; '.join(active),'Inactive_Qualifications':'; '.join(inactive),
      'Qualification_Details':joined(q),'Qualification_Details_JSON':json.dumps(q),
      'Life_Status':life[2],'Life_Issue_Date':iso(life[1]),'Years_Since_Life_Issue':years(life[1],asof),
      'Life_Status_Date':iso(life[3]),'Life_Expiration_Date':iso(life[4]),
      'Days_Until_Life_Expiration':(datetime.strptime(life[4],'%m/%d/%Y').date()-asof).days,
      'Earliest_Displayed_Qualification_Issue':iso(issued),'Years_Since_Earliest_Displayed_Issue':years(issued,asof),
      'Experience_Measure_Note':'Elapsed time since displayed issue dates; not actual working years, continuous licensing or policy production.',
      'Active_Health_Authority':'Yes' if 'Accident & Health or Sickness' in active else 'No',
      'Active_PC_Authority':'Yes' if any(t in active for t in ['Property','Casualty','Personal Lines']) else 'No',
      'Variable_Authority_Status':next((r[2] for r in q if 'Var Life' in r[0]),'Not displayed'),
      'Current_Business_Address':f['business_address'],'Current_Business_Phone':phone,
      'Phone_Source':'Current CDI record' if phone else 'No phone displayed on current CDI record',
      'Phone_Directness':'Unverified' if phone else 'No number displayed','Toll_Free_Number':'Yes' if tollfree else 'No' if phone else 'Not available',
      'Contact_Readiness':contact,'Reported_Languages':'; '.join(languages),
      'Appointed_Insurers':'; '.join(names),'Unique_Insurer_Count':len(names),'Appointment_Row_Count':len(a),
      'Life_Appointed_Insurers':'; '.join(lnames),'Unique_Life_Insurer_Count':len(lnames),
      'Health_Appointed_Insurers':'; '.join(uniq(r[0] for r in a if 'Health' in r[1])),
      'PC_Appointed_Insurers':'; '.join(uniq(r[0] for r in a if r[1] in ['Property','Casualty','Personal Lines'])),
      'Appointment_Details':joined(a),'Appointment_Details_JSON':json.dumps(a),
      'Agency_Organizations':'; '.join(gnames),'Unique_Agency_Count':len(gnames),
      'Life_Agency_Organizations':'; '.join(lg),'Agency_Relationship_Details':joined(g),'Agency_Relationships_JSON':json.dumps(g),
      'Latest_Displayed_Relationship_Date':iso(last),'Other_Relationship_Tables_JSON':json.dumps(f['other_relationship_tables']),
      'Enforcement_Entries_Displayed':len(f['orders']),'Enforcement_Details':joined(f['orders']) or 'None displayed',
      'Complaint_Entries_Displayed':len(f['complaints']),'Complaint_Details':joined(f['complaints']) or 'None displayed',
      'Excluded_Relationships':joined(matches),'Bank_Securities_Agency_Finding':'No bank/securities agency identified in displayed entries',
      'Agency_Research_Source':agency_sources,'Recruiting_Priority':priority,
      'Actual_Target_Product_Sales':'Not established by licensing page','Historical_Father_Approval':'Not evaluated against this new cohort; screen result only',
      'Data_Notes':'; '.join(flags),'Screening_Status':'PASS' if passed else 'FAIL',
      'Rule_Basis':'Final operating rules dated 2026-10-08',
      'AI_Input_Data':json.dumps({'license_number':lic,'source_url':row['license_url'],'checked_on':asof.isoformat(),'qualifications':q,'appointments':a,'agencies':g,'phone':phone,'rules_version':'Final 2026-10-08'}),
      'AI_Row_Assessment':assessment,
      'Assessment_Method':'Codex reviewed this row independently using extracted live CDI facts; no separate API agent call.',
      'Passed_Test':'Yes' if passed else 'No',
    }
    row.update(added);enriched.append(row)
assert len(enriched)==10
assert list(enriched[0])[-1]=='Passed_Test'
(CACHE/'enriched-rows.json').write_text(json.dumps(enriched,indent=2),encoding='utf-8')
print(json.dumps({'rows':len(enriched),'columns':len(enriched[0]),'pass':sum(r['Passed_Test']=='Yes' for r in enriched),'fail':sum(r['Passed_Test']=='No' for r in enriched)},indent=2))
