import csv,json,re
from pathlib import Path
from datetime import datetime
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'exports/next-fifty-test'
with (ROOT/'output/csv/cdi-agents-simplified-first-10-enriched.csv').open(encoding='utf-8-sig',newline='') as f:
    rows=list(csv.DictReader(f))
data=json.loads((CACHE/'facts.json').read_text())
research=json.loads((CACHE/'agency-research.json').read_text()) if (CACHE/'agency-research.json').exists() else {}
def uniq(xs):return list(dict.fromkeys(xs))
def iso(s):return datetime.strptime(s,'%m/%d/%Y').date().isoformat() if s else ''
health=re.compile(r'ANTHEM|BLUE SHIELD|HEALTH NET|KAISER|AETNA|HUMANA|UNITEDHEALTH|CIGNA|HEALTH PLAN',re.I)
audit=[]
for i,entry in enumerate(data,10):
    row=rows[i];assert row['License_Number']==entry['input']['license_number']
    row['Checked_On']='2026-10-08'
    if entry['error'] or not entry.get('facts',{}).get('qualifications'):
        row['Rationale']='Not verified: licensing record needs review; no confirmed exclusion.'
        row['Passed_Test']='No';row['Recruiting_Priority']='Needs review'
        audit.append({'row':i+1,'status':'REVIEW','error':entry['error']});continue
    f=entry['facts'];q=f['qualifications'];appointments=f['appointments'];agencies=f['agencies']
    life=next((x for x in q if x[0]=='Life' and x[2]=='Active'),next((x for x in q if x[0]=='Life'),None))
    active=[x[0] for x in q if x[2]=='Active']
    insurers=uniq(x[0] for x in appointments);orgs=uniq(x[0] for x in agencies)
    life_insurers=uniq(x[0] for x in appointments if x[1]=='Life');life_agencies=uniq(x[0] for x in agencies if x[1]=='Life')
    excluded=uniq(x[0] for x in appointments+agencies if re.search(r'\bSTATE FARM\b|\bFARMERS\b|\bALLSTATE\b|\bKNIGHTS OF COLUMBUS\b|\bTHRIVENT\b',x[0],re.I))
    excluded+=uniq(x for x in orgs if research.get(x,{}).get('classification')=='Bank/securities agency')
    orders=f['orders']
    uncertainty=[x for x in orgs if research.get(x,{}).get('classification')=='Unresolved']
    if life is None or life[2]!='Active':
        passed=False;status='FAIL';priority='Not eligible';reason='Excluded: no active general Life qualification displayed.'
        if any('Funeral' in x or 'Burial' in x for x in active):reason='Excluded: funeral/burial-only authority does not qualify for the general Life pool.'
    elif excluded:
        passed=False;status='FAIL';priority='Not eligible';reason='Excluded: current '+'; '.join(excluded)+' relationship.'
        for label,pattern in [('State Farm',r'\bSTATE FARM\b'),('Farmers',r'\bFARMERS\b'),('Allstate',r'\bALLSTATE\b')]:
            if any(re.search(pattern,x,re.I) for x in excluded):reason='Excluded: current '+label+' relationship.';break
        else:
            if any(research.get(x,{}).get('classification')=='Bank/securities agency' for x in excluded):
                short=next((label for label in ['Wells Fargo','Raymond James','LPL','Morgan Stanley'] if any(label.upper() in x for x in excluded)),'bank/securities agency')
                reason='Excluded: current '+short+' bank/securities agency relationship.'
    elif uncertainty:
        passed=False;status='REVIEW';priority='Needs review';reason='Not verified: agency classification needs review for '+'; '.join(uncertainty)+'.'
    else:
        passed=True;status='PASS'
        wfg=any('WORLD FINANCIAL GROUP' in x for x in orgs)
        primerica=any('PRIMERICA' in x for x in orgs+insurers)
        nonhealth_life=[x for x in life_insurers if not health.search(x)]
        priority='Higher' if nonhealth_life or life_agencies or wfg or primerica else 'Lower'
        if wfg:reason='Eligible WFG producer with active Life and no excluded relationships.'
        elif primerica:reason='Eligible Primerica producer with active Life and no excluded relationships.'
        elif any('NEW YORK LIFE' in x or 'NYLIFE' in x for x in life_insurers+orgs):reason='Active Life with accepted New York Life/NYLIFE relationships; no excluded relationship found.'
        elif nonhealth_life:reason='Active Life with Life-insurer appointments and no excluded relationships.'
        elif life_agencies:reason='Active Life with a listed Life agency relationship and no excluded relationships.'
        elif not appointments and not agencies:reason='Active Life with no listed relationships; eligible at lower priority.'
        else:reason='Active Life with only health/auto-home relationships displayed; eligible at lower priority.'
    row.update({
      'Business_Address':f['business_address'],'Business_Phone':f['business_phone'],
      'Languages':'; '.join(uniq(x.strip() for x in f['languages'].split(',') if x.strip())),
      'Active_Qualifications':'; '.join(active),
      'Life_Issue_Date':iso(life[1]) if life else '',
      'Years_Since_Life_Issue':round((datetime(2026,10,8).date()-datetime.strptime(life[1],'%m/%d/%Y').date()).days/365.2425,2) if life else '',
      'Life_Expiration_Date':iso(life[4]) if life else '',
      'Appointed_Companies':'; '.join(insurers),'Agencies':'; '.join(orgs),
      'Recruiting_Priority':priority,'Contact_Status':'Do not contact - excluded' if status=='FAIL' else 'Needs review' if status=='REVIEW' else 'Find contact' if not f['business_phone'] else 'Verify direct number',
      'Rationale':reason,'Passed_Test':'Yes' if passed else 'No',
    })
    audit.append({'row':i+1,'license_number':row['License_Number'],'status':status,'exclusions':excluded,'orders':orders,'research':[research.get(x,{}) for x in orgs],'source_url':row['License_URL'],'checked_at_utc':entry['checked_at_utc']})
phones=Counter(r['Business_Phone'] for r in rows[:60] if r['Business_Phone'])
for row in rows[10:60]:
    if row['Passed_Test']=='Yes' and row['Business_Phone']:
        digits=re.sub(r'\D','',row['Business_Phone'])
        if len(digits)==11 and digits[0]=='1':digits=digits[1:]
        if digits[:3] in ['800','888','877','866','855','844','833','822']:row['Contact_Status']='Find direct number - toll-free'
        elif phones[row['Business_Phone']]>1:row['Contact_Status']='Find direct number - shared listing'
(CACHE/'compact-rows.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
(CACHE/'screening-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps({'new_rows':len(audit),'new_results':dict(Counter(x['status'] for x in audit)),'total_evaluated':60,'total_yes':sum(x['Passed_Test']=='Yes' for x in rows),'total_no':sum(x['Passed_Test']=='No' for x in rows),'new_exclusions':[{k:x[k] for k in ['row','license_number','exclusions']} for x in audit if x['status']=='FAIL']},indent=2))
