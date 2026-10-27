'use strict';
// Bounded public-document collection. Never visits a provider or downloads video.
const fs=require('fs'),path=require('path');
const r=require('./lib/backup-rules.cjs'),p=require('./lib/fast-rules.cjs'),{Http}=require('./lib/fast-http.cjs');
const HOME=__dirname,DATA=path.resolve(process.env.ZZ_DATA||path.join(HOME,'state'));
const read=(file,fallback)=>fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):fallback;
function save(file,value){fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file+'.tmp',JSON.stringify(value));fs.renameSync(file+'.tmp',file);}
async function run(){
 fs.mkdirSync(DATA,{recursive:true});const now=Date.now(),known=new Map(read(path.join(HOME,'catalogue.json'),[]).map(x=>[x.url,x]));
 const state=read(path.join(DATA,'observations.json'),{schema:1,episodes:{},listings:{},pending:[]});
 if(state.schema!==1)throw Error('Unexpected state schema');
 const java=fs.readFileSync(path.join(HOME,'java/AnimeFlvSource.java'),'utf8'),groups=[...java.match(/SCOPED_FAMILIES=\{(.+?)\};/)[1].matchAll(/\{([^}]+)\}/g)].map(x=>[...x[1].matchAll(/"([^"]+)"/g)].map(y=>y[1]));
 const roots={mega:'mega.nz',streamwish:'streamwish.com',vidhide:'vidhide.com',mixdrop:'mxdrop.click',mp4upload:'mp4upload.com',streamtape:'streamtape.com'},policy=Object.fromEntries(Object.entries(roots).map(([n,h])=>[n,groups.find(g=>g.includes(h))||[]]));
 if(Object.values(policy).some(x=>!x.length))throw Error('Incomplete provider policy');
 let browser,context,home;
 const transport={};
 if(process.env.ZZ_BROWSER==='true'){
  const {chromium}=require('playwright');browser=await chromium.launch({headless:true});context=await browser.newContext();const page=await context.newPage();
  await page.route('**/*',route=>{const q=route.request();let allowed=false;try{const u=new URL(q.url());allowed=u.protocol==='https:'&&['jkanime.net','www.jkanime.net'].includes(u.hostname)&&['document','script','xhr','fetch','stylesheet'].includes(q.resourceType());}catch{}return allowed?route.continue():route.abort();});
  try{const response=await page.goto('https://jkanime.net/',{waitUntil:'domcontentloaded',timeout:30000});if(response.status()!==200)throw Error('Normal browser refused HTTP '+response.status());home=await page.content();}
  catch(e){await browser.close();const report={sourceAvailable:false,normalBrowser:true,detail:String(e.message).replace(/https?:\/\/\S+/g,'[source]').slice(0,160),newEpisodes:0};save(path.join(DATA,'collection-status.json'),report);save(path.join(DATA,'observations.json'),state);console.log(JSON.stringify(report));throw e;}
  transport.fetch=async(url,opts)=>{
   if(home!==undefined&&url==='https://jkanime.net/'){const text=home;home=undefined;return {status:200,headers:new Headers({'content-type':'text/html'}),body:[Buffer.from(text)]};}
   const headers={...opts.headers};delete headers['User-Agent'];delete headers.Cookie;
   const response=await context.request.fetch(url,{method:opts.method||'GET',headers,data:opts.body,maxRedirects:0,timeout:20000});const body=await response.body();if(body.length>4*1024*1024)throw Error('Document limit exceeded');
   return {status:response.status(),headers:new Headers(response.headers()),body:[body]};
  };
 }
 const http=new Http(500,{cooldownFile:path.join(DATA,'cooldown.json'),...transport});let budget=0;
 const get=http.get.bind(http);http.get=async(...args)=>{if(++budget>240)throw Object.assign(Error('Hourly request budget reached'),{stop:true});return get(...args);};
 const pending=new Set(state.pending),stats={schema:1,checkedAt:new Date(now).toISOString(),source:'jkanime.net',newEpisodes:0,reused:0,issues:0,unknownSeries:0,aiCalls:0,mediaDownloaded:false};
 try{
  const html=await http.get('https://jkanime.net/');
  for(const m of html.matchAll(/href=["'](https:\/\/(?:www\.)?jkanime\.net\/[a-zA-Z0-9_-]+\/[1-9][0-9]*\/)["']/g)){const url=r.episode(m[1]);if(url)pending.add(url);}
  // Refresh only observations approaching the real app's seven-day expiry.
  for(const [url,ep] of Object.entries(state.episodes)){if(now-Date.parse(ep.observedAt)>6*86400000)pending.add(url);}
  const refreshed=new Map();let attempted=0;
  for(const url of [...pending]){
   const parent=r.series(url.replace(/\/[0-9]+\/$/,'/')),row=known.get(parent);
   if(!parent||r.episode(url,parent)!==url){pending.delete(url);continue;}
   if(!row||!p.normal(row.title)){stats.unknownSeries++;continue;}
   const old=state.episodes[url];
   if(old?.complete&&now-Date.parse(old.observedAt)<6*86400000){pending.delete(url);stats.reused++;continue;}
   if(attempted++>=(process.env.ZZ_PROOF==='true'?2:120))break;
   try{
    let listing=state.listings[parent];
    if(!listing?.complete||!listing.episodes.includes(url)||now-Date.parse(listing.observedAt)>6*86400000){
     if(!refreshed.has(parent))refreshed.set(parent,await require('./lib/fast-listing.cjs').listing(http,row));
     listing=refreshed.get(parent);
    }
    if(listing.series!==parent||!listing.complete||!listing.episodes.includes(url)||listing.episodes.some(u=>r.episode(u,parent)!==u))throw Error('Observed listing does not confirm chapter');
    const html=await http.get(url);p.identity(html,row.title,Number(url.match(/\/(\d+)\/$/)[1]));const data=p.providers(html,policy);
    if(!data.complete)throw Error('Incomplete provider observation');
    state.listings[parent]=listing;state.episodes[url]={archiveVersion:3,episode:url,observedAt:new Date().toISOString(),...data,playbackVerified:false};pending.delete(url);stats.newEpisodes++;
    state.pending=[...pending];save(path.join(DATA,'observations.json'),state);
   }catch(e){stats.issues++;if(e.stop)throw e;}
  }
  stats.sourceAvailable=true;
 }catch(e){stats.sourceAvailable=false;stats.failure=e.stop?'source_limit_or_budget':'source_unavailable';stats.detail=String(e.message).replace(/https?:\/\/\S+/g,'[source]').slice(0,140);}
 state.pending=[...pending];stats.pending=state.pending.length;stats.requests=http.requests;save(path.join(DATA,'observations.json'),state);save(path.join(DATA,'collection-status.json'),stats);console.log(JSON.stringify(stats));
 if(browser)await browser.close();if(!stats.sourceAvailable)process.exitCode=2;
}
if(require.main===module)run().catch(()=>{console.error('Collection rejected; prior public data retained');process.exitCode=1;});
module.exports={run};
