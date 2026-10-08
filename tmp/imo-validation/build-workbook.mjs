import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root='C:/Users/arthu/cdi-scraper', out=root+'/outputs/imo-validation', qa=root+'/tmp/imo-validation';
const data=JSON.parse(await fs.readFile(out+'/validation-data.json','utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('Summary'), life=wb.worksheets.add('Life review'), other=wb.worksheets.add('Other licenses'), rules=wb.worksheets.add('Rules');
const cols=[['name','Name',30],['license','License',13],['original','Original list',14],['decision','Draft screen',14],['reviewer_decision','Reviewer decision',19],['actual_reason','Actual reason / correction',45],['reviewer_evidence','Reviewer evidence / missing fact',45],['reviewer_name_date','Reviewer / date',23],['review_question','Question for reviewer',65],['rule_ids','Draft rule IDs',15],['why','Observable explanation; motive unknown',65],['historical_reason_status','Historical reason status',36],['prior_tier','Earlier priority tier',17],['prior_route','Earlier priority route',43],['life_status','Life status',16],['life_issued','Life issued',15],['life_expires','Life expires',15],['other_active','All active qualifications',43],['phone','Business phone',18],['phone_source','Phone source',42],['address','Business address',45],['residency','Residency',16],['search_state','Search state',14],['agency','Agencies / qualification / effective date',65],['appointments','Insurers / qualification / effective date',80],['orders','Enforcement / date',60],['complaints','Complaints',50],['sponsors','Sponsors / qualification / date',50],['employers','Employer relationships',50],['positive','Positive signals',65],['flags','All contextual concerns',80],['tenure','Life issue-date tenure (years)',24],['expiry_days','Life expiry (days from check)',24],['recent_appointment','Latest Life appointment',24],['languages','Reported languages',25],['original_pdf_group','Original PDF heading',45],['pdf_phone','Original PDF phone',20],['pdf_name','Original PDF name',35],['aliases','Search names / aliases',55],['source','Direct CDI source',80],['check_date','Evidence checked',18],['cache_sha256','Cached source SHA-256',70]];
cols.push(['all_qualifications','All qualifications / status / issue / status date / expiry',80],['search_status','Overall search status',22],['name_source','Name source',45]);
function letter(n){let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;}
for(const sh of [summary,life,other,rules]){sh.showGridLines=false;sh.tabColor=sh===summary?'#243B53':sh===rules?'#7A8793':'#52718B';}
function base(sh,range){sh.getRange(range).format.font.name='Arial';sh.getRange(range).format.font.size=10;sh.getRange(range).format.verticalAlignment='center';}
function header(sh,range){const f=sh.getRange(range).format;f.fill='#243B53';f.font.color='#FFFFFF';f.font.bold=true;f.wrapText=true;f.rowHeight=36;f.horizontalAlignment='center';}
function buildRecords(sh,records,label){
 const last=records.length+5, end=letter(cols.length-1);base(sh,`A2:${end}${last}`);
 sh.getRange('A2').values=[[label]];sh.getRange('A2').format.font.size=14;sh.getRange('A2').format.font.bold=true;
 sh.getRange('A3').values=[['Amber E:H = reviewer input. Original membership stays unchanged. Filter tier 1 + Omitted for the 35 first-call discrepancies.']];
 sh.getRange('A3').format.font.italic=true;sh.getRange('A3').format.font.size=10;
 sh.getRange(`A5:${end}5`).values=[cols.map(x=>x[1])];
 sh.getRange(`A6:${end}${last}`).values=records.map(r=>cols.map(([k])=>r[k]??''));
 sh.getRange(`B6:B${last}`).formulas=records.map(r=>['="'+r.license+'"']);
 sh.tables.add(`A5:${end}${last}`,true,sh===life?'LifeReviewTable':'OtherLicensesTable');
 for(let i=0;i<cols.length;i++)sh.getRange(`${letter(i)}5:${letter(i)}${last}`).format.columnWidth=cols[i][2];
 sh.getRange(`A6:${end}${last}`).format.rowHeight=52;sh.getRange(`A6:${end}${last}`).format.wrapText=true;
 header(sh,`A5:${end}5`);sh.getRange(`E6:H${last}`).format.fill='#FFF2CC';
 sh.getRange(`B6:B${last}`).setNumberFormat('0000000');sh.getRange(`S6:S${last}`).setNumberFormat('@');sh.getRange(`AK6:AK${last}`).setNumberFormat('@');
 sh.getRange(`AF6:AF${last}`).setNumberFormat('0.0');sh.getRange(`AG6:AG${last}`).setNumberFormat('0');
 sh.getRange(`E6:E${last}`).dataValidation={rule:{type:'list',values:['Pending','Approve','Reject','Defer','Not reviewed']}};
 sh.getRange(`D6:D${last}`).conditionalFormats.add('containsText',{text:'FAIL',format:{fill:'#FCE4D6',font:{color:'#9C0006'}}});
 sh.getRange(`D6:D${last}`).conditionalFormats.add('containsText',{text:'REVIEW',format:{fill:'#FFF2CC'}});
 sh.freezePanes.freezeRows(5);sh.freezePanes.freezeColumns(3);
 return last;
}
const lifeRecords=data.records.filter(r=>r.active_life), otherRecords=data.records.filter(r=>!r.active_life);
const ll=buildRecords(life,lifeRecords,'Active-Life review • 202 omitted + 136 approved controls');
const ol=buildRecords(other,otherRecords,'Other licenses • 1,347 qualification mismatches + 20 unverifiable records');
base(summary,'A2:H32');summary.getRange('A2').values=[['IMO recruiting experiment']];summary.getRange('A2').format.font.size=14;summary.getRange('A2').format.font.bold=true;
summary.getRange('A3').values=[['Evidence: October 8, 2026. Approval PDFs: October 5. Membership is known; historical motives remain unconfirmed.']];
summary.getRange('A3').format.font.italic=true;
summary.getRange('A5:D5').values=[['Active-Life screen','Approved','Omitted','Total']];header(summary,'A5:D5');
for(let i=0;i<3;i++){
 const row=6+i, status=['PASS','REVIEW','FAIL'][i];summary.getRange(`A${row}`).values=[[status]];
 for(let j=0;j<2;j++)summary.getRange(`${letter(j+1)}${row}`).formulas=[[`=COUNTIFS('Life review'!$C$6:$C$${ll},"${j?'Omitted':'Approved'}",'Life review'!$D$6:$D$${ll},A${row})`]];
 summary.getRange(`D${row}`).formulas=[[`=SUM(B${row}:C${row})`]];
}
summary.getRange('A9').values=[['Total active Life']];summary.getRange('B9:D9').formulas=[['=SUM(B6:B8)','=SUM(C6:C8)','=SUM(D6:D8)']];summary.getRange('A9:D9').format.font.bold=true;
summary.getRange('A11:B15').values=[['Other omitted licenses',otherRecords.length],['Total unique licenses',data.records.length],['Earlier first-call omissions',35],['Retrieved detail failures',0],['Unverifiable qualifications',20]];
summary.getRange('F5:H5').values=[['Reviewer progress','Life','Other']];header(summary,'F5:H5');
for(let i=0;i<5;i++){const row=6+i,s=['Pending','Approve','Reject','Defer','Not reviewed'][i];summary.getRange(`F${row}`).values=[[s]];summary.getRange(`G${row}`).formulas=[[`=COUNTIF('Life review'!$E$6:$E$${ll},F${row})`]];summary.getRange(`H${row}`).formulas=[[`=COUNTIF('Other licenses'!$E$6:$E$${ol},F${row})`]];}
const notes=[['How to use','Enter answers once, in the amber fields of the two record sheets.'],['Review first','Life review: filter Original list = Omitted and Earlier priority tier = 1.'],['Every omission','Review all 202 active-Life omissions and 20 unverifiable records; bulk-confirm the 1,347 qualification mismatches only after checking scope.'],['Actual reasons','Reject requires the real reason and evidence. Defer requires the missing fact. Not reviewed is different from rejected.'],['Approved controls','Approved examples prevent universal P&C, variable, health-carrier, nonresident, and historical-order exclusions.'],['Draft screen','PASS / FAIL / REVIEW is provisional and distinct from the supplied PDF approval.'],['Sources','Exact URLs, check dates, all qualification/relationship fields, original PDF contacts, and cached-page hashes are in each record.'],['Rule confirmation','Rules tab records proposed scope. Record reviewer confirmation and exceptions; only confirmed rules may become automatic exclusions.'],['No accuracy claim','This is retrospective reconstruction. Validate adjudicated rules on a different surname before using them at scale.']];
summary.getRange('A17:B25').values=notes;summary.getRange('A17:A25').format.font.bold=true;summary.getRange('B17:H25').merge(true);for(let i=0;i<notes.length;i++)summary.getRange(`B${17+i}`).values=[[notes[i][1]]];summary.getRange('B17:H25').format.wrapText=true;summary.getRange('A17:H25').format.rowHeight=38;
summary.getRange('A5:A25').format.columnWidth=29;summary.getRange('B5:B25').format.columnWidth=17;summary.getRange('C5:D25').format.columnWidth=12;summary.getRange('E5:E25').format.columnWidth=3;summary.getRange('F5:F25').format.columnWidth=25;summary.getRange('G5:H25').format.columnWidth=12;
base(rules,'A2:I30');rules.getRange('A2').values=[['Provisional rule register • reviewer confirmation required']];rules.getRange('A2').format.font.size=14;rules.getRange('A2').format.font.bold=true;
rules.getRange('A3').values=[['Counts are approved / omitted; active-Life denominators 136 / 202 except L1. Factors overlap. Amber fields are editable.']];
const ruleHeader=['ID','Factor','Draft action','Evidence / confidence','Observed counts','Guardrail','Reviewer status','Confirmed scope / exception','Reviewer / date'];
rules.getRange('A5:I5').values=[ruleHeader];rules.getRange(`A6:I${data.rules.length+5}`).values=data.rules.map(r=>[...r,'Unconfirmed','','']);header(rules,'A5:I5');
rules.tables.add(`A5:I${data.rules.length+5}`,true,'RulesTable');rules.getRange(`A6:I${data.rules.length+5}`).format.wrapText=true;rules.getRange(`A6:I${data.rules.length+5}`).format.rowHeight=85;
for(let i=0;i<9;i++)rules.getRange(`${letter(i)}5:${letter(i)}30`).format.columnWidth=[9,29,45,35,35,60,20,60,24][i];
rules.getRange('G7').values=[['User-confirmed']];rules.getRange(`G6:I${data.rules.length+5}`).format.fill='#FFF2CC';rules.getRange(`G6:G${data.rules.length+5}`).dataValidation={rule:{type:'list',values:['Unconfirmed','User-confirmed','Confirmed','Revised','Rejected']}};rules.freezePanes.freezeRows(5);
await wb.recalculate();
console.log((await wb.inspect({kind:'region',sheetId:'Summary',range:'A5:H14',maxChars:3000,tableMaxRows:11,tableMaxCols:8})).ndjson);
const output=await SpreadsheetFile.exportXlsx(wb);await output.save(out+'/IMO_Producer_Review.xlsx');
for(const [name,range] of [['Summary','A2:H25'],['Life review','A5:E10'],['Other licenses','A5:E10'],['Rules','A5:E10']]){
 const preview=await wb.render({sheetName:name,range,scale:1.5,format:'png'});await fs.writeFile(qa+'/'+name.replaceAll(' ','-')+'.png',new Uint8Array(await preview.arrayBuffer()));
}
console.log('Workbook exported with',lifeRecords.length+otherRecords.length,'distinct records.');
