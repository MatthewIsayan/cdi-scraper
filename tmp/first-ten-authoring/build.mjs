import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook} from '@oai/artifact-tool';
const root='C:/Users/arthu/cdi-scraper';
const cache=process.argv[2]||'first-ten-test';
const evaluated=Number(process.argv[3]||10);
const sheetName=`First ${evaluated}`;
const rows=JSON.parse(await fs.readFile(path.join(root,`exports/${cache}/compact-rows.json`),'utf8'));
const fields=Object.keys(rows[0]);
const matrix=[fields,...rows.map(r=>fields.map(k=>r[k]??''))];
const book=Workbook.create();
const sheet=book.worksheets.add(sheetName);
sheet.getRangeByIndexes(0,0,matrix.length,fields.length).values=matrix;
sheet.getRangeByIndexes(0,0,matrix.length,fields.length).format.font={name:'Arial',size:10};
sheet.getRangeByIndexes(0,0,1,fields.length).format={fill:'#243B53',font:{name:'Arial',bold:true,color:'#FFFFFF'}};
sheet.getRange('A1:A11').format.columnWidth=32;
function col(n){let s='';for(n++;n>0;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;}
const last=col(fields.length-1);
sheet.getRange(`${last}1:${last}11`).format.columnWidth=20;
book.recalculate();
const values=sheet.getRangeByIndexes(0,0,matrix.length,fields.length).values;
if(values.length!==403||values[0].at(-1)!=='Passed_Test'||values[0].at(-2)!=='License_URL')throw Error('Output shape invalid');
if(values.slice(1,evaluated+1).some(r=>!['Yes','No'].includes(r.at(-1))))throw Error('Invalid final result');
if(values.slice(evaluated+1).some(r=>r.at(-1)))throw Error('Rows beyond requested count evaluated');
console.log((await book.inspect({kind:'table',range:`'${sheetName}'!${last}12:${last}21`,include:'values',tableMaxRows:10,tableMaxCols:1})).ndjson);
for(const [label,range] of [['names','A12:A21'],['results',`${last}12:${last}21`]]){
    const preview=await book.render({sheetName,range,scale:1.5,format:'png'});
    await fs.writeFile(path.join(root,`tmp/first-ten-authoring/${label}.png`),new Uint8Array(await preview.arrayBuffer()));
}
const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
const csv='\uFEFF'+values.map(row=>row.map(quote).join(',')).join('\r\n')+'\r\n';
const output=path.join(root,`output/csv/cdi-agents-simplified-first-${evaluated}-enriched.csv`);
await fs.mkdir(path.dirname(output),{recursive:true});
await fs.writeFile(output,csv,'utf8');
console.log(JSON.stringify({output,rows:rows.length,columns:fields.length,lastColumn:fields.at(-1)}));
