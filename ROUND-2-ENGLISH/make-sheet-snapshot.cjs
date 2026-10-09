const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
let handler;
const source = path.join(__dirname, 'live-sheet.cjs');
vm.runInNewContext(fs.readFileSync(source, 'utf8'), {
  __dirname,
  require: name => name === 'node:http' ? {
    createServer: fn => { handler = fn; return { listen() {} }; }
  } : require(name),
  console
});
let html;
handler({url:'/'}, {setHeader(){},end(value){html=value;}});
const csv = path.join(__dirname,'exports','cdi-agents.csv');
const data = JSON.stringify({csv:fs.readFileSync(csv,'utf8'),modified:fs.statSync(csv).mtime.toISOString()}).replace(/</g,'\\u003c');
html = html.replace("let response=await fetch('/data',{cache:'no-store'});if(!response.ok)throw Error('CSV unavailable');let data=await response.json(),parsed=parse(data.csv);", `let data=${data},parsed=parse(data.csv);`)
  .replace('refresh();setInterval(refresh,5000);','refresh();')
  .replace('refreshes every 5 seconds','portable snapshot · does not refresh')
  .replace('Round two · English agents','Round two · English agents · snapshot');
const target = path.join(__dirname,'English-agents-snapshot.html');
fs.writeFileSync(target,html);
fs.copyFileSync(csv,path.join(__dirname,'English-agents-snapshot.csv'));
console.log(target);
