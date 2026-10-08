const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const csv = path.join(__dirname, 'exports', 'cdi-agents.csv');
const html = `<!doctype html><meta charset="utf-8"><title>Round two live sheet</title>
<style>body{font:14px system-ui;margin:24px;color:#182638}input,button{padding:8px;margin:4px}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}th{background:#edf2f7;position:sticky;top:0}#status{color:#526278}</style>
<h1>Round two · English agents</h1><p id="status">Loading…</p><input id="search" placeholder="Search name, license, ZIP…" size="40"><button id="prev">Previous</button><button id="next">Next</button><span id="page"></span><div style="overflow:auto"><table><thead id="head"></thead><tbody id="body"></tbody></table></div>
<script>
let rows=[],headers=[],page=0;
function parse(text){let out=[],row=[],field='',quoted=false;for(let i=0;i<text.length;i++){let c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){field+='"';i++}else quoted=!quoted}else if(c===','&&!quoted){row.push(field);field=''}else if(c==='\\n'&&!quoted){row.push(field.replace(/\\r$/,''));out.push(row);row=[];field=''}else field+=c}if(field||row.length){row.push(field);out.push(row)}return out}
function render(){let q=document.getElementById('search').value.toLowerCase(),filtered=rows.filter(r=>r.join(' ').toLowerCase().includes(q)),count=Math.max(1,Math.ceil(filtered.length/100));page=Math.min(page,count-1);document.getElementById('page').textContent='Page '+(page+1)+' / '+count+' · '+filtered.length+' matches';let columns=headers;document.getElementById('head').replaceChildren();let tr=document.createElement('tr');columns.forEach(c=>{let th=document.createElement('th');th.textContent=c.replaceAll('_',' ');tr.append(th)});document.getElementById('head').append(tr);let body=document.getElementById('body');body.replaceChildren();filtered.slice(page*100,page*100+100).forEach(r=>{let tr=document.createElement('tr');columns.forEach(c=>{let td=document.createElement('td');let value=r[headers.indexOf(c)]||'';if(c.endsWith('_url')&&/^https?:/.test(value)){let a=document.createElement('a');a.href=value;a.target='_blank';a.rel='noopener noreferrer';a.textContent=c==='license_url'?'CDI record':'Directions';td.append(a)}else if(c==='raw_text'){let details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Original directory text';details.append(summary);let content=document.createElement('div');content.textContent=value;content.style.whiteSpace='pre-wrap';details.append(content);td.append(details)}else{td.textContent=value}tr.append(td)});body.append(tr)})}
async function refresh(){try{let response=await fetch('/data',{cache:'no-store'});if(!response.ok)throw Error('CSV unavailable');let data=await response.json(),parsed=parse(data.csv);headers=parsed.shift()||[];rows=parsed;render();document.getElementById('status').textContent=rows.length+' saved agents · CSV updated '+new Date(data.modified).toLocaleString()+' · refreshes every 5 seconds'}catch(e){document.getElementById('status').textContent='Waiting for CSV: '+e.message}}
document.getElementById('search').oninput=()=>{page=0;render()};document.getElementById('prev').onclick=()=>{page=Math.max(0,page-1);render()};document.getElementById('next').onclick=()=>{page++;render()};refresh();setInterval(refresh,5000);
</script>`;
http.createServer((req,res)=>{
  res.setHeader('Cache-Control','no-store');
  if(req.url==='/data'){try{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({csv:fs.readFileSync(csv,'utf8'),modified:fs.statSync(csv).mtime.toISOString()}))}catch{res.statusCode=503;res.end('CSV unavailable')}}
  else if(req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html)}
  else{res.statusCode=404;res.end()}
}).listen(8766,'127.0.0.1',()=>console.log('Live sheet: http://127.0.0.1:8766'));

