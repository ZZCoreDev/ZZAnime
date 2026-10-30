// ZZAnime help chain (task 10). The signed channel lists the chapters the cloud lacks ("wanted");
// devices answer only those, in batches. An option is offered to the cloud only after two devices on
// two different networks (Cloudflare ASN) sent it and its real file name matches the chapter.
// No IP, account or device identifier is stored in clear; everything expires after 8 days.
export const EPISODE=/^https:\/\/jkanime\.net\/[a-zA-Z0-9_-]+\/[1-9][0-9]*\/$/;
const DAY=86400000,KEEP=8*DAY,RECHECK=6*3600000,MAX_ITEMS=20,MAX_OPTIONS=8,MAX_INSPECT=30,MAX_WANTED=400,WANTED_TTL=120000,ENOUGH_OPTIONS=2;
const ACCEPTED=new Set(['name-match','quorum3']);
const STOP=new Set(['the','and','season','temporada','part','movie','hen']);
const enc=new TextEncoder();
export const iso=t=>new Date(t).toISOString();
export async function sha(text){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(text)))].map(b=>b.toString(16).padStart(2,'0')).join('');}
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json','cache-control':'no-store'}});
// Mirrors ProviderPlaybackPolicy.family in the app; the cloud still runs the real app validator.
export function family(name){
 const n=String(name||'').trim().toLowerCase();
 if(/^streamtape?(?:[\s0-9:()_-].*)?$/.test(n))return 'streamtape';
 for(const f of ['desu','magi','mega','streamwish','vidhide','mixdrop','mp4upload'])if(new RegExp('^'+f+'(?:[\\s0-9:()_-].*)?$').test(n))return f;
 return '';
}
const norm=s=>String(s||'').normalize('NFKD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
// 'match' needs series words and the chapter number; 'mismatch' means series words with another number.
export function nameVerdict(name,entry){
 const slug=entry.url.split('/')[3].replace(/-/g,' '),words=[...new Set(norm(entry.title+' '+slug).split(' '))].filter(w=>w.length>=3&&!/^[0-9]+$/.test(w)&&!STOP.has(w));
 const n=norm(name),compact=n.replace(/ /g,''),hits=words.filter(w=>compact.includes(w)).length;
 const series=words.length>0&&hits>=Math.min(2,words.length),number=new RegExp('(^|[^0-9])0*'+entry.number+'([^0-9]|$)').test(n);
 return series&&number?'match':series?'mismatch':'unknown';
}
const b64url=s=>Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/').padEnd(Math.ceil(s.length/4)*4,'=')),c=>c.charCodeAt(0));
export function megaLink(url){
 const m=/^https:\/\/(?:www\.)?mega\.(?:nz|co\.nz)\/(?:(?:file|embed)\/([A-Za-z0-9_-]{8})#([A-Za-z0-9_-]{43})|(?:embed)?#!([A-Za-z0-9_-]{8})!([A-Za-z0-9_-]{43}))$/.exec(url);
 return m?{id:m[1]||m[3],key:m[2]||m[4]}:null;
}
// Decrypts the file attributes the same way mega.nz does (AES-CBC, zero IV, zero padding).
// WebCrypto only accepts PKCS#7, so one crafted block is appended that decrypts to a full pad.
export async function megaName(url,fetcher){
 const link=megaLink(url);if(!link)return null;
 const k=b64url(link.key);if(k.length!==32)return null;const raw=new Uint8Array(16);for(let i=0;i<16;i++)raw[i]=k[i]^k[i+16];
 const r=await fetcher('https://g.api.mega.co.nz/cs?id='+Math.floor(Math.random()*1e9),{method:'POST',body:JSON.stringify([{a:'g',p:link.id}]),headers:{'content-type':'application/json'}});
 if(!r.ok)return undefined;const body=await r.json(),file=Array.isArray(body)?body[0]:body;
 if(typeof file==='number'||!file||typeof file.at!=='string')return null;
 const at=b64url(file.at);if(!at.length||at.length%16)return null;
 const key=await crypto.subtle.importKey('raw',raw,'AES-CBC',false,['encrypt','decrypt']);
 const pad=new Uint8Array(await crypto.subtle.encrypt({name:'AES-CBC',iv:at.slice(-16)},key,new Uint8Array(16).fill(16))).slice(0,16);
 const joined=new Uint8Array(at.length+16);joined.set(at);joined.set(pad,at.length);
 const text=new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-CBC',iv:new Uint8Array(16)},key,joined)).replace(/\0+$/,'');
 if(!text.startsWith('MEGA{'))return null;
 try{const n=JSON.parse(text.slice(4)).n;return typeof n==='string'?n:null;}catch{return null;}
}
async function pageTitle(url,fetcher){
 const r=await fetcher(url,{headers:{'user-agent':'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36'},redirect:'follow',signal:AbortSignal.timeout(8000)});
 if(!r.ok)return null;const html=(await r.text()).slice(0,262144);
 const m=/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']{1,300})/i.exec(html)||/<title[^>]*>([^<]{1,300})<\/title>/i.exec(html);return m?m[1]:null;
}
// 'match' | 'mismatch' | 'dead' | 'unknown'. Only MEGA is decisive when the provider cannot be read.
export async function inspect(option,entry,fetcher){
 try{
  if(option.family==='mega'){const name=await megaName(option.url,fetcher);if(name===null)return {verdict:'dead'};if(name===undefined)return {verdict:'unknown'};const v=nameVerdict(name,entry);return {verdict:v==='unknown'?'mismatch':v,detail:name.slice(0,200)};}
  // A readable title that names some numbered video other than this chapter is a mismatch, not unknown.
  const title=await pageTitle(option.url,fetcher);if(!title)return {verdict:'unknown'};const v=nameVerdict(title,entry);
  return {verdict:v==='unknown'&&/[0-9]/.test(title)?'mismatch':v,detail:title.slice(0,200)};
 }catch{return {verdict:'unknown'};}
}
// Wanted list straight from the signed channel the apps read; stale or unsigned channels ask for nothing.
let cached={at:0,map:null};
export async function loadWanted(env,now=Date.now(),fetcher=fetch){
 if(cached.map&&now-cached.at<WANTED_TTL)return cached.map;
 const r=env.CHANNEL?await env.CHANNEL.fetch('https://channel/channel.json'):await fetcher(env.CHANNEL_URL,{cf:{cacheTtl:60}});
 if(!r.ok)throw new Error('channel '+r.status);
 const wrapper=await r.json(),sig=wrapper.signature;if(!/^[a-f0-9]{512}$/.test(sig))throw new Error('channel signature encoding');
 const key=await crypto.subtle.importKey('spki',Uint8Array.from(atob(env.PUBLIC_KEY),c=>c.charCodeAt(0)),{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
 if(!await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,Uint8Array.from(sig.match(/../g),h=>parseInt(h,16)),enc.encode(wrapper.payload)))throw new Error('channel signature');
 const payload=JSON.parse(wrapper.payload),age=now-Date.parse(payload.createdAt),map=new Map();
 if(payload.schema===1&&age>=-300000&&age<=DAY&&Array.isArray(payload.wanted))for(const w of payload.wanted.slice(0,MAX_WANTED))if(EPISODE.test(w.url)&&Number.isInteger(w.number))map.set(w.url,w);
 cached={at:now,map};return map;
}
export function resetWanted(){cached={at:0,map:null};}
// Hashed network zone (IPv4 /24, IPv6 /48): only compared with others, never stored in clear.
export async function zone(ip,salt){
 const v4=/^(\d+)\.(\d+)\.(\d+)\.\d+$/.exec(ip||'');
 const z=v4?v4.slice(1,4).join('.'):(ip||'').includes(':')?(ip.split(':').slice(0,3).join(':')):'';
 return z?await sha(salt+'|zone|'+z):'';
}
// Storage lives in one SQLite-backed Durable Object (free plan: 100k rows written a day). One row per
// chapter and device; options are tallied per chapter and a decision is written once per option.
// Every method is synchronous, so each call is atomic.
export class Store{
 constructor(sql){this.sql=sql;
  sql.exec('DROP TABLE IF EXISTS submissions');sql.exec('DROP TABLE IF EXISTS checks');
  sql.exec('CREATE TABLE IF NOT EXISTS seen(episode TEXT,device TEXT,asn INTEGER,created INTEGER,options TEXT,PRIMARY KEY(episode,device))');
  sql.exec('CREATE TABLE IF NOT EXISTS decided(episode TEXT,okey TEXT,name TEXT,family TEXT,url TEXT,devices INTEGER,asns INTEGER,first INTEGER,verdict TEXT,checked INTEGER,PRIMARY KEY(episode,okey))');
  sql.exec('CREATE TABLE IF NOT EXISTS counters(k TEXT PRIMARY KEY,n INTEGER,expires INTEGER)');
  sql.exec('CREATE TABLE IF NOT EXISTS dead(okey TEXT,episode TEXT,name TEXT,family TEXT,url TEXT,device TEXT,asn INTEGER,created INTEGER,PRIMARY KEY(okey,device))');
  // Columns added after the first deployment; an existing column just raises and is ignored.
  for(const q of ['ALTER TABLE seen ADD COLUMN zone TEXT','ALTER TABLE decided ADD COLUMN zones INTEGER'])try{sql.exec(q);}catch{}}
 rows(q,...p){return this.sql.exec(q,...p).toArray();}
 take(limits,expires){
  for(const [k,limit,w] of limits){const r=this.rows('SELECT n FROM counters WHERE k=?',k)[0];if((r?r.n:0)+w>limit)return false;}
  for(const [k,,w] of limits)this.sql.exec('INSERT INTO counters(k,n,expires) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET n=n+?',k,w,expires,w);
  return true;
 }
 note(day,counts,expires){
  for(const [k,n] of Object.entries(counts))if(n)this.sql.exec('INSERT INTO counters(k,n,expires) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET n=n+?','stat:'+day+':'+k,n,expires,n);
  return true;
 }
 tally(episode){
  const out=new Map();
  for(const r of this.rows('SELECT device,asn,zone,created,options FROM seen WHERE episode=?',episode))for(const o of JSON.parse(r.options)){
   let t=out.get(o.okey);if(!t){t={...o,devices:new Set(),asns:new Set(),zones:new Set(),first:r.created};out.set(o.okey,t);}
   t.devices.add(r.device);t.asns.add(r.asn);if(r.zone)t.zones.add(r.zone);t.first=Math.min(t.first,r.created);
  }
  return out;
 }
 // Two devices on two networks (ASN). With sameAsnZones>0, the same network also counts when that many
 // devices come from as many different zones; that path is accepted only on a matching file name.
 static quorum(t,sameAsnZones){return t.devices.size>=2&&(t.asns.size>=2||(sameAsnZones>0&&t.devices.size>=sameAsnZones&&t.zones.size>=sameAsnZones));}
 // Stores each new answer and returns the options that just reached quorum and still need their file
 // name checked. A chapter with enough accepted options answers 'enough'.
 submit(items,limits,expires,now,sameAsnZones=0){
  if(!this.take(limits,expires))return {limited:true};
  const status={},inspect=[];
  for(const it of items){
   const decided=new Map(this.rows('SELECT okey,verdict,checked FROM decided WHERE episode=?',it.episode).map(r=>[r.okey,r]));
   if([...decided.values()].filter(r=>ACCEPTED.has(r.verdict)).length>=ENOUGH_OPTIONS){status[it.episode]='enough';continue;}
   const known=this.rows('SELECT 1 AS x FROM seen WHERE episode=? AND device=?',it.episode,it.device).length>0;
   if(!known)this.sql.exec('INSERT INTO seen(episode,device,asn,created,options,zone) VALUES(?,?,?,?,?,?)',it.episode,it.device,it.asn,now,JSON.stringify(it.options),it.zone||'');
   status[it.episode]=known?'duplicate':'stored';
   for(const t of this.tally(it.episode).values()){
    if(!Store.quorum(t,sameAsnZones))continue;
    const d=decided.get(t.okey),c={episode:it.episode,okey:t.okey,name:t.name,family:t.family,url:t.url,devices:t.devices.size,asns:t.asns.size,zones:t.zones.size,first:t.first};
    if(d&&d.verdict!=='unknown')continue;
    if(d&&t.family!=='mega'&&c.asns>=3){this.decide([{...c,verdict:'unknown'}],now);continue;}
    if(d&&now-d.checked<RECHECK)continue;
    inspect.push(c);
   }
  }
  return {status,inspect};
 }
 decide(results,now){
  for(const r of results){
   const verdict=r.verdict==='match'?'name-match':r.verdict==='unknown'&&r.family!=='mega'&&r.asns>=3?'quorum3':r.verdict;
   this.sql.exec('INSERT OR REPLACE INTO decided(episode,okey,name,family,url,devices,asns,first,verdict,checked,zones) VALUES(?,?,?,?,?,?,?,?,?,?,?)',r.episode,r.okey,r.name,r.family,r.url,r.devices,r.asns,r.first,verdict,now,r.zones||0);
  }
  return results.length;
 }
 // Forgets chapters that are no longer wanted (filled or rotated out) and returns accepted options.
 accepted(episodes,now){
  const list=JSON.stringify(episodes);
  this.sql.exec('DELETE FROM seen WHERE created<? OR episode NOT IN (SELECT value FROM json_each(?))',now-KEEP,list);
  this.sql.exec('DELETE FROM decided WHERE first<? OR episode NOT IN (SELECT value FROM json_each(?))',now-KEEP,list);
  this.sql.exec('DELETE FROM counters WHERE expires<?',now);
  return this.rows("SELECT episode,name,family,url,devices,asns,zones,first,verdict FROM decided WHERE verdict IN ('name-match','quorum3') ORDER BY episode,first");
 }
 dead(items,limits,expires,now){
  if(!this.take(limits,expires))return {limited:true};
  const status={};
  for(const it of items){
   const known=this.rows('SELECT 1 AS x FROM dead WHERE okey=? AND device=?',it.okey,it.device).length>0;
   if(!known)this.sql.exec('INSERT INTO dead VALUES(?,?,?,?,?,?,?,?)',it.okey,it.episode,it.name,it.family,it.url,it.device,it.asn,now);
   status[it.url]=known?'duplicate':'stored';
  }
  return {status};
 }
 // Two devices are enough here: a report only moves the link to the front of the cloud link checker,
 // which decides on its own reading and controls.
 deadReports(now){
  this.sql.exec('DELETE FROM dead WHERE created<?',now-KEEP);
  return this.rows('SELECT episode,name,family,url,COUNT(DISTINCT device) AS devices,COUNT(DISTINCT asn) AS asns,MIN(created) AS first FROM dead GROUP BY okey HAVING devices>=2 ORDER BY devices DESC,first LIMIT 300');
 }
 stats(now,sameAsnZones=0){
  const day=Math.floor(now/DAY),start=day*DAY,one=(q,...p)=>this.rows(q,...p)[0]||{};
  const counter=k=>one('SELECT n FROM counters WHERE k=?',k).n||0;
  const verdicts=Object.fromEntries(this.rows('SELECT verdict,COUNT(*) AS n FROM decided GROUP BY verdict').map(r=>[r.verdict,r.n]));
  const quorum={waitingSecondDevice:0,sameNetworkOnly:0,reached:0};let episodes=0;
  for(const {episode} of this.rows('SELECT DISTINCT episode FROM seen')){
   episodes++;
   for(const t of this.tally(episode).values())quorum[t.devices.size<2?'waitingSecondDevice':Store.quorum(t,sameAsnZones)?'reached':'sameNetworkOnly']++;
  }
  return {day:iso(start).slice(0,10),
   today:{devices:one('SELECT COUNT(DISTINCT device) AS n FROM seen WHERE created>=?',start).n||0,networks:one('SELECT COUNT(DISTINCT asn) AS n FROM seen WHERE created>=?',start).n||0,
    answers:one('SELECT COUNT(*) AS n FROM seen WHERE created>=?',start).n||0,requests:one('SELECT SUM(n) AS n FROM counters WHERE k LIKE ? AND expires=?','ip:%',(day+2)*DAY).n||0,
    items:counter('day:'+day),stop:counter('stat:'+day+':stop'),unsupported:counter('stat:'+day+':unsupported'),limited:counter('stat:'+day+':limited'),
    deadReports:one('SELECT COUNT(*) AS n FROM dead WHERE created>=?',start).n||0},
   pendingEpisodes:episodes,quorum,verdicts,sameAsnZones,
   deadCandidates:this.rows('SELECT okey FROM dead GROUP BY okey HAVING COUNT(DISTINCT device)>=2').length};
 }
}
async function body(request,limit){const text=await request.text();if(text.length>limit)throw new Error('too large');return JSON.parse(text);}
function same(a,b){if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let d=0;for(let i=0;i<a.length;i++)d|=a.charCodeAt(i)^b.charCodeAt(i);return d===0;}
const LINK=/^https:\/\/[a-z0-9.-]+\.[a-z]{2,}\//i;
async function options(list){
 const out=[],seen=new Set();
 for(const o of (Array.isArray(list)?list:[]).slice(0,MAX_OPTIONS)){
  const f=family(o?.name),link=String(o?.url||'');
  if(!f||typeof o.name!=='string'||o.name.length>70||!LINK.test(link)||link.length>500)continue;
  const okey=await sha(o.name+'\0'+link);if(!seen.has(okey)){seen.add(okey);out.push({okey,name:o.name,family:f,url:link});}
 }
 return out;
}
function authorized(request,env){return !!env.HELP_KEY&&same(request.headers.get('authorization')||'','Bearer '+env.HELP_KEY);}
export async function handle(request,env,store,deps={}){
 const now=(deps.now||Date.now)(),fetcher=deps.fetch||fetch,url=new URL(request.url),day=Math.floor(now/DAY),expires=(day+2)*DAY;
 const sameAsnZones=Math.max(0,Number(env.SAME_ASN_ZONES||0));
 if(request.method==='POST'&&(url.pathname==='/v1/submit'||url.pathname==='/v1/dead')){
  // submit: {"schema":1,"device":"<random id>","items":[{"episode":url,"options":[{"name","url"}]}]}; per-item answer:
  // stored | duplicate | enough (drop it, enough devices answered) | stop (not wanted any more) | unsupported.
  // dead:   {"schema":1,"device":"<random id>","items":[{"episode":url,"name","url"}]}; answer per url.
  let x;try{x=await body(request,32768);}catch{return json({accepted:false,reason:'bad-request'},400);}
  if(x?.schema!==1||!/^[A-Za-z0-9_-]{16,64}$/.test(x.device||'')||!Array.isArray(x.items)||!x.items.length||x.items.length>MAX_ITEMS)return json({accepted:false,reason:'bad-request'},400);
  const asn=Number(request.cf?.asn)||0;if(!asn)return json({accepted:false,reason:'no-network'},400);
  const ip=request.headers.get('cf-connecting-ip')||'',device=await sha(env.SALT+'|device|'+x.device);
  const ipKey='ip:'+await sha(env.SALT+'|ip|'+day+'|'+ip),result={},valid=[];
  const limits=n=>[[ipKey,Number(env.IP_LIMIT||200),1],[(url.pathname==='/v1/dead'?'deadday:':'day:')+day,Number(env.DAILY_CAP||40000),n]];
  if(url.pathname==='/v1/dead'){
   for(const it of x.items){
    const name=String(it?.name||''),link=String(it?.url||''),f=family(name)||(/^voe\b/i.test(name.trim())?'voe':'');
    if(!EPISODE.test(it?.episode||'')||!f||name.length>70||!LINK.test(link)||link.length>500){if(link)result[link.slice(0,500)]='unsupported';continue;}
    valid.push({okey:await sha(name+'\0'+link),episode:it.episode,name,family:f,url:link,device,asn});
   }
   if(valid.length){const r=await store.dead(valid,limits(valid.length),expires,now);if(r.limited)return json({accepted:false,reason:'limit'},429);Object.assign(result,r.status);}
   return json({accepted:true,items:Object.entries(result).map(([u,status])=>({url:u,status}))});
  }
  const wanted=await loadWanted(env,now,fetcher),zoneHash=await zone(ip,env.SALT),counts={stop:0,unsupported:0};
  for(const it of x.items){
   if(!EPISODE.test(it?.episode||'')||result[it.episode])continue;
   if(!wanted.has(it.episode)){result[it.episode]='stop';counts.stop++;continue;}
   const opts=await options(it.options);if(!opts.length){result[it.episode]='unsupported';counts.unsupported++;continue;}
   valid.push({episode:it.episode,device,asn,zone:zoneHash,options:opts});
  }
  if(valid.length){
   const r=await store.submit(valid,limits(valid.length),expires,now,sameAsnZones);
   if(r.limited){await store.note(day,{limited:1},expires);return json({accepted:false,reason:'limit'},429);}
   Object.assign(result,r.status);const done=[];
   for(const c of r.inspect.slice(0,MAX_INSPECT)){
    // A same-network quorum (asns<2) can only pass on a matching file name: decide() needs 3 networks for quorum3.
    done.push({...c,verdict:(await inspect(c,wanted.get(c.episode),fetcher)).verdict});
   }
   if(done.length)await store.decide(done,now);
  }
  if(counts.stop||counts.unsupported)await store.note(day,counts,expires);
  return json({accepted:true,items:Object.entries(result).map(([episode,status])=>({episode,status}))});
 }
 if(request.method==='GET'&&url.pathname==='/v1/accepted'){
  if(!authorized(request,env))return json({error:'unauthorized'},401);
  const wanted=await loadWanted(env,now,fetcher),out=new Map();
  for(const r of await store.accepted([...wanted.keys()],now)){
   const entry=wanted.get(r.episode);if(!entry)continue;
   const row=out.get(r.episode)||{url:r.episode,acceptedAt:iso(r.first),...(entry.firstSeenAt?{firstSeenAt:entry.firstSeenAt}:{}),...(entry.renew?{renew:true}:{}),options:[]};
   if(r.first<Date.parse(row.acceptedAt))row.acceptedAt=iso(r.first);
   row.options.push({name:r.name,family:r.family,url:r.url,devices:r.devices,asns:r.asns,zones:r.zones||0,check:r.verdict});out.set(r.episode,row);
  }
  return json({schema:1,generatedAt:iso(now),episodes:[...out.values()]});
 }
 if(request.method==='GET'&&url.pathname==='/v1/dead-reports'){
  if(!authorized(request,env))return json({error:'unauthorized'},401);
  return json({schema:1,generatedAt:iso(now),links:await store.deadReports(now)});
 }
 if(request.method==='GET'&&url.pathname==='/v1/stats'){
  if(!authorized(request,env))return json({error:'unauthorized'},401);
  return json({schema:1,generatedAt:iso(now),...await store.stats(now,sameAsnZones)});
 }
 if(request.method==='GET'&&url.pathname==='/')return new Response('ZZAnime ayuda entre dispositivos.',{headers:{'content-type':'text/plain; charset=utf-8'}});
 return json({error:'not-found'},404);
}
