const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const {DatabaseSync}=require('node:sqlite');
const root=__dirname;
function tail(file,n){try{return fs.readFileSync(file,'utf8').trim().split(/\r?\n/).slice(-n);}catch{return [];}}
function status(){
 const db=new DatabaseSync(path.join(root,'data','agents.db'),{readOnly:true});
 let agents,searches,recovery,problems;
 try{db.exec('PRAGMA busy_timeout=1000');agents=db.prepare('SELECT COUNT(*) AS n FROM agents').get().n;searches=Object.fromEntries(db.prepare('SELECT status,COUNT(*) AS n FROM searches GROUP BY status').all().map(r=>[r.status,r.n]));recovery=db.prepare('SELECT COUNT(DISTINCT child_zip) AS n FROM cap_recovery').get().n;problems=db.prepare("SELECT zip,city,status,error FROM searches WHERE status IN ('error','in_progress')").all();}finally{db.close();}
 const supervisor=tail(path.join(root,'logs','supervisor.log'),8);
 const files=fs.readdirSync(path.join(root,'logs')).filter(n=>/^supervised-.*\.log$/.test(n)).sort();
 const activity=files.length?tail(path.join(root,'logs',files.at(-1)),12):[];
 const latest=supervisor.at(-1)||'';
 const phase=/Supervisor stopped|Stop file found|manual review|budget exhausted/i.test(latest)?'Stopped':/cooldown/i.test(latest)?'Cooldown':'Started / running';
 return {agents,searches,recovery,problems,phase,supervisor,activity,checked:new Date().toISOString()};
}
http.createServer((req,res)=>{
 res.setHeader('Cache-Control','no-store');
 if(req.url==='/status'){try{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(status()));}catch(e){res.statusCode=503;res.end(JSON.stringify({error:e.message}));}}
 else if(req.url==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(fs.readFileSync(path.join(root,'live-status.html')));}
 else {res.statusCode=404;res.end('Not found');}
}).listen(8767,'127.0.0.1',()=>console.log('Live status: http://127.0.0.1:8767'));
