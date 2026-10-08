import json,re
from pathlib import Path
from lxml import html
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'exports/first-ten-test'
def clean(s):return ' '.join(s.split())
def table(tree,id):
    nodes=tree.xpath('//table[@id=$id]',id=id)
    if not nodes:return []
    return [[clean(td.text_content()) for td in tr.xpath('./td')] for tr in nodes[0].xpath('.//tr[td]')]
results=[]
for entry in json.loads((CACHE/'source-rows.json').read_text()):
    row=entry['input'];path=CACHE/(row['license_number']+'.html')
    if entry['error']:results.append(entry);continue
    tree=html.fromstring(path.read_text(encoding='utf-8'))
    heads=[clean(x.text_content()) for x in tree.xpath('//h3')]
    facts={'name':next((s[5:].strip() for s in heads if s.startswith('Name:')),''),'qualifications':table(tree,'licenseDetailGrid'),'appointments':table(tree,'AppointmentGrid'),'agencies':table(tree,'EndorsingOrganizationsGrid'),'orders':table(tree,'EnforcementActionGrid'),'complaints':table(tree,'ConsumerComplaintGrid')}
    for label,key in [('Business Address:','business_address'),('Business Phone:','business_phone'),('Language:','languages')]:
        vals=tree.xpath('//*[self::div or self::b][contains(text(),$label)]',label=label)
        if vals:
            node=vals[0]
            if node.tag=='b':node=node.getparent()
            value=clean(node.text_content())
            facts[key]=value.split(label,1)[-1].strip()
        else:facts[key]=''
    facts['other_relationship_tables']={x.get('id'):table(tree,x.get('id')) for x in tree.xpath('//table[@id]') if x.get('id') not in ['licenseDetailGrid','AppointmentGrid','EndorsingOrganizationsGrid','EnforcementActionGrid','ConsumerComplaintGrid']}
    facts['headings']=heads
    entry['facts']=facts
    results.append(entry)
(CACHE/'facts.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
for x in results:
    print(json.dumps({'license':x['input']['license_number'],**x.get('facts',{})},ensure_ascii=False))
