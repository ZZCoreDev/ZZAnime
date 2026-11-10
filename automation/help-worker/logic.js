// ZZAnime help chain (task 10). The signed channel lists the chapters the cloud lacks ("wanted");
// devices answer only those, in batches. An option is offered to the cloud only after two devices on
// two different networks (Cloudflare ASN) sent it and its real file name matches the chapter.
// No IP, account or device identifier is stored in clear; everything expires after 8 days.
import {SUBMIT_POLICY_VERSION,submitUrlAllowed} from './submit-policy.js';
import {boundedText,InspectionPolicyError,MEGA_BYTES} from './bounded-fetch.js';
import {sessionUser} from './session.js';
export const EPISODE=/^https:\/\/jkanime\.net\/[a-zA-Z0-9_-]+\/[1-9][0-9]*\/$/;
// S2: a device counts only after MIN_DEVICE_AGE; a network can introduce at most NEW_DEVICES_PER_NET devices a day.
const MIN_DEVICE_AGE=24*3600000,NEW_DEVICES_PER_NET=5,SIGNAL_POLICY={evidencePolicy:'network-v2',basis:'independent-networks',minDeviceAgeHours:24};
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
function optionAllowed(o){return typeof o?.name==='string'&&o.name.length<=70&&o.family===family(o.name)&&submitUrlAllowed(o.family,o.url);}
function currentDecision(r){return r.policy===SUBMIT_POLICY_VERSION&&optionAllowed(r);}
const norm=s=>String(s||'').normalize('NFKD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
// 'match' needs series words and the chapter number; 'mismatch' means series words with another number.
// Held entries ("held":true: a JK /1/ that redirects to the series' OVA/movie page) need the series words
// only: movie and OVA files rarely carry «1». Quorum and approved providers are unchanged.
export function nameVerdict(name,entry){
 const slug=entry.url.split('/')[3].replace(/-/g,' '),words=[...new Set(norm(entry.title+' '+slug).split(' '))].filter(w=>w.length>=3&&!/^[0-9]+$/.test(w)&&!STOP.has(w));
 const n=norm(name),compact=n.replace(/ /g,''),hits=words.filter(w=>compact.includes(w)).length;
 const series=words.length>0&&hits>=Math.min(2,words.length),number=entry.held===true||new RegExp('(^|[^0-9])0*'+entry.number+'([^0-9]|$)').test(n);
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
 if(!submitUrlAllowed('mega',url))throw new InspectionPolicyError('destination');
 const link=megaLink(url);if(!link)return null;
 const k=b64url(link.key);if(k.length!==32)return null;const raw=new Uint8Array(16);for(let i=0;i<16;i++)raw[i]=k[i]^k[i+16];
 const api='https://g.api.mega.co.nz/cs?id='+Math.floor(Math.random()*1e9);
 const text=await boundedText(api,{method:'POST',body:JSON.stringify([{a:'g',p:link.id}]),headers:{'content-type':'application/json'}},fetcher,u=>u===api,{maxBytes:MEGA_BYTES,maxRedirects:0});
 if(text===null)return undefined;const body=JSON.parse(text),file=Array.isArray(body)?body[0]:body;
 if(typeof file==='number'||!file||typeof file.at!=='string')return null;
 const at=b64url(file.at);if(!at.length||at.length%16)return null;
 const key=await crypto.subtle.importKey('raw',raw,'AES-CBC',false,['encrypt','decrypt']);
 const pad=new Uint8Array(await crypto.subtle.encrypt({name:'AES-CBC',iv:at.slice(-16)},key,new Uint8Array(16).fill(16))).slice(0,16);
 const joined=new Uint8Array(at.length+16);joined.set(at);joined.set(pad,at.length);
 const plain=new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-CBC',iv:new Uint8Array(16)},key,joined)).replace(/\0+$/,'');
 if(!plain.startsWith('MEGA{'))return null;
 try{const n=JSON.parse(plain.slice(4)).n;return typeof n==='string'?n:null;}catch{return null;}
}
async function pageTitle(option,fetcher){
 const html=await boundedText(option.url,{headers:{'user-agent':'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36'}},fetcher,u=>submitUrlAllowed(option.family,u));
 if(html===null)return null;
 const m=/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']{1,300})/i.exec(html)||/<title[^>]*>([^<]{1,300})<\/title>/i.exec(html);return m?m[1]:null;
}
// 'match' | 'mismatch' | 'dead' | 'unknown'. Only MEGA is decisive when the provider cannot be read.
export async function inspect(option,entry,fetcher){
 const result=verdict=>({verdict,policy:SUBMIT_POLICY_VERSION});
 if(!optionAllowed(option))return result('policy-rejected');
 try{
  if(option.family==='mega'){const name=await megaName(option.url,fetcher);if(name===null)return result('dead');if(name===undefined)return result('unknown');const v=nameVerdict(name,entry);return {...result(v==='unknown'?'mismatch':v),detail:name.slice(0,200)};}
  // A readable title that names some numbered video other than this chapter is a mismatch, not unknown.
  const title=await pageTitle(option,fetcher);if(!title)return result('unknown');const v=nameVerdict(title,entry);
  return {...result(v==='unknown'&&/[0-9]/.test(title)?'mismatch':v),detail:title.slice(0,200)};
 }catch(error){return result(error instanceof InspectionPolicyError?'policy-rejected':'unknown');}
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
  // Schema changes are additive: keep legacy tables and their evidence intact.
  sql.exec('CREATE TABLE IF NOT EXISTS seen(episode TEXT,device TEXT,asn INTEGER,created INTEGER,options TEXT,PRIMARY KEY(episode,device))');
  sql.exec('CREATE TABLE IF NOT EXISTS decided(episode TEXT,okey TEXT,name TEXT,family TEXT,url TEXT,devices INTEGER,asns INTEGER,first INTEGER,verdict TEXT,checked INTEGER,PRIMARY KEY(episode,okey))');
  sql.exec('CREATE TABLE IF NOT EXISTS counters(k TEXT PRIMARY KEY,n INTEGER,expires INTEGER)');
  // One row per option, device and day: a device votes once a day per option (played or failed).
  sql.exec('CREATE TABLE IF NOT EXISTS plays(okey TEXT,device TEXT,day INTEGER,episode TEXT,name TEXT,family TEXT,url TEXT,ok INTEGER,fail INTEGER,PRIMARY KEY(okey,device,day))');
  // Intro/ending marks: one per chapter, kind and device; accepted when two devices agree within 3 s.
  sql.exec('CREATE TABLE IF NOT EXISTS marks(episode TEXT,kind TEXT,device TEXT,day INTEGER,start INTEGER,stop INTEGER,PRIMARY KEY(episode,kind,device))');
  sql.exec('CREATE TABLE IF NOT EXISTS dead(okey TEXT,episode TEXT,name TEXT,family TEXT,url TEXT,device TEXT,asn INTEGER,created INTEGER,PRIMARY KEY(okey,device))');
  // Columns added after the first deployment; an existing column just raises and is ignored.
  for(const q of ['ALTER TABLE seen ADD COLUMN zone TEXT','ALTER TABLE decided ADD COLUMN zones INTEGER',"ALTER TABLE decided ADD COLUMN policy TEXT NOT NULL DEFAULT ''"])try{sql.exec(q);}catch{}
  sql.exec('CREATE TABLE IF NOT EXISTS devices(device TEXT PRIMARY KEY,net TEXT,first INTEGER)');for(const q of ['ALTER TABLE plays ADD COLUMN net TEXT','ALTER TABLE marks ADD COLUMN net TEXT'])try{sql.exec(q);}catch{}}
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
   if(!optionAllowed(o))continue;
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
   // A renewal reading is the evidence /v1/renewals reports: keep this device's latest reading of the page (date and
   // options), even when the chapter already has enough options or the device had read it before.
   if(it.renew)this.sql.exec('INSERT INTO seen(episode,device,asn,created,options,zone) VALUES(?,?,?,?,?,?) ON CONFLICT(episode,device) DO UPDATE SET created=excluded.created,options=excluded.options,asn=excluded.asn,zone=excluded.zone',it.episode,it.device,it.asn,now,JSON.stringify(it.options.filter(optionAllowed)),it.zone||'');
   const decided=new Map(this.rows('SELECT okey,verdict,checked,name,family,url,policy FROM decided WHERE episode=?',it.episode).map(r=>[r.okey,r]));
   if([...decided.values()].filter(r=>currentDecision(r)&&ACCEPTED.has(r.verdict)).length>=ENOUGH_OPTIONS){status[it.episode]='enough';continue;}
   const known=this.rows('SELECT 1 AS x FROM seen WHERE episode=? AND device=?',it.episode,it.device).length>0;
   if(!known)this.sql.exec('INSERT INTO seen(episode,device,asn,created,options,zone) VALUES(?,?,?,?,?,?)',it.episode,it.device,it.asn,now,JSON.stringify(it.options.filter(optionAllowed)),it.zone||'');
   status[it.episode]=known&&!it.renew?'duplicate':'stored';
   for(const t of this.tally(it.episode).values()){
    if(!Store.quorum(t,sameAsnZones))continue;
    const previous=decided.get(t.okey),d=previous&&currentDecision(previous)?previous:null,c={episode:it.episode,okey:t.okey,name:t.name,family:t.family,url:t.url,devices:t.devices.size,asns:t.asns.size,zones:t.zones.size,first:t.first};
    if(d&&d.verdict!=='unknown')continue;
    if(d&&t.family!=='mega'&&c.asns>=3){this.decide([{...c,verdict:'unknown',policy:SUBMIT_POLICY_VERSION}],now);continue;}
    if(d&&now-d.checked<RECHECK)continue;
    inspect.push(c);
   }
  }
  return {status,inspect};
 }
 decide(results,now){
  for(const r of results){
   const safe=optionAllowed(r)&&r.policy===SUBMIT_POLICY_VERSION;
   const verdict=!safe?'policy-rejected':r.verdict==='match'?'name-match':r.verdict==='unknown'&&r.family!=='mega'&&r.asns>=3?'quorum3':r.verdict;
   this.sql.exec('INSERT OR REPLACE INTO decided(episode,okey,name,family,url,devices,asns,first,verdict,checked,zones,policy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',r.episode,r.okey,r.name,r.family,r.url,r.devices,r.asns,r.first,verdict,now,r.zones||0,safe?SUBMIT_POLICY_VERSION:'');
  }
  return results.length;
 }
 // Forgets chapters that are no longer wanted (filled or rotated out) and returns accepted options.
 accepted(episodes,now){
  const list=JSON.stringify(episodes);
  this.sql.exec('DELETE FROM seen WHERE created<? OR episode NOT IN (SELECT value FROM json_each(?))',now-KEEP,list);
  this.sql.exec('DELETE FROM decided WHERE first<? OR episode NOT IN (SELECT value FROM json_each(?))',now-KEEP,list);
  this.sql.exec('DELETE FROM counters WHERE expires<?',now);
  return this.rows("SELECT episode,name,family,url,devices,asns,zones,first,verdict,policy FROM decided WHERE verdict IN ('name-match','quorum3') ORDER BY episode,first").filter(currentDecision);
 }
 // Renewal evidence: what single devices saw for chapters the cloud asked to renew (latest answer per chapter).
 // The cloud only uses it to re-confirm links it already approved; it never adds a link from it.
 renewEvidence(episodes){
  if(!episodes.length)return [];const out=new Map();
  // One row per chapter (its latest answer) and a hard cap keep this inside the free plan's CPU budget.
  for(const r of this.rows('SELECT episode,MAX(created) AS created,options FROM seen WHERE episode IN (SELECT value FROM json_each(?)) GROUP BY episode LIMIT 200',JSON.stringify(episodes.slice(0,400)))){
   let options=[];try{options=JSON.parse(r.options).filter(optionAllowed).slice(0,MAX_OPTIONS).map(o=>({name:o.name,family:o.family,url:o.url}));}catch{}
   if(options.length)out.set(r.episode,{url:r.episode,observedAt:iso(r.created),options});
  }
  return [...out.values()];
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
 // Writes only when the device's vote for that option and day is new or changes, so repeats cost nothing.
 play(items,limits,expires,day){
  if(!this.take(limits,expires))return {limited:true};
  const status={};
  for(const it of items){
   if(!this.admitDevice(it.device,it.net,it.now)){status[it.url]='new-device-limit';continue;}
   const r=this.rows('SELECT ok,fail FROM plays WHERE okey=? AND device=? AND day=?',it.okey,it.device,day)[0],ok=it.ok?1:0,fail=it.ok?0:1;
   if(!r)this.sql.exec('INSERT INTO plays(okey,device,day,episode,name,family,url,ok,fail,net) VALUES(?,?,?,?,?,?,?,?,?,?)',it.okey,it.device,day,it.episode,it.name,it.family,it.url,ok,fail,it.net);
   else if((ok&&!r.ok)||(fail&&!r.fail))this.sql.exec('UPDATE plays SET ok=MAX(ok,?),fail=MAX(fail,?),net=? WHERE okey=? AND device=? AND day=?',ok,fail,it.net,it.okey,it.device,day);
   status[it.url]=r?'duplicate':'stored';
  }
  return {status};
 }
 // S2: a device can join a network's signals once known; new devices need a network and stay under that network's daily limit.
 admitDevice(device,net,now){
  if(!net)return false;if(this.rows('SELECT 1 AS x FROM devices WHERE device=?',device).length)return true;
  const today=Math.floor(now/DAY)*DAY;if(this.rows('SELECT COUNT(*) AS n FROM devices WHERE net=? AND first>=?',net,today)[0].n>=NEW_DEVICES_PER_NET)return false;
  this.sql.exec('INSERT INTO devices(device,net,first) VALUES(?,?,?)',device,net,now);return true;
 }
 // Option and family success counts (one verdict per network, 14 days) and series popularity (distinct networks, 7 days).
 // Only devices older than MIN_DEVICE_AGE count; rows without a network (stored before S2) never count.
 playStats(now){
  const day=Math.floor(now/DAY);this.sql.exec('DELETE FROM plays WHERE day<?',day-13);const mature=now-MIN_DEVICE_AGE,LIMIT=200000;
  const votes=this.rows("SELECT p.okey AS okey,p.family AS family,p.net AS net,MAX(p.ok) AS ok FROM plays p JOIN devices d ON d.device=p.device WHERE p.net IS NOT NULL AND p.net<>'' AND d.first<=? GROUP BY p.okey,p.net LIMIT ?",mature,LIMIT+1);
  const seen=this.rows("SELECT DISTINCT p.episode AS episode,p.net AS net FROM plays p JOIN devices d ON d.device=p.device WHERE p.day>=? AND p.net IS NOT NULL AND p.net<>'' AND d.first<=? LIMIT ?",day-6,mature,LIMIT+1);
  const byOption=new Map(),families={};
  for(const v of votes.slice(0,LIMIT)){let o=byOption.get(v.okey);if(!o)byOption.set(v.okey,o={key:v.okey,family:v.family,ok:0,fail:0});if(v.ok)o.ok++;else o.fail++;const fam=families[v.family]||(families[v.family]=[0,0]);fam[v.ok?0:1]++;}
  const options=[...byOption.values()].map(o=>({...o,independentNetworks:o.ok+o.fail})).filter(o=>o.independentNetworks>=3).sort((a,b)=>b.independentNetworks-a.independentNetworks||(a.key<b.key?-1:1)).slice(0,3000);
  const viewers=new Map();for(const r of seen.slice(0,LIMIT)){const series=r.episode.replace(/[0-9]+\/$/,'');let set=viewers.get(series);if(!set)viewers.set(series,set=new Set());set.add(r.net);}
  const popular=[...viewers].map(([series,set])=>({series,devices:set.size,independentNetworks:set.size})).filter(x=>x.independentNetworks>=2).sort((a,b)=>b.independentNetworks-a.independentNetworks||(a.series<b.series?-1:1)).slice(0,100);
  return {...SIGNAL_POLICY,complete:votes.length<=LIMIT&&seen.length<=LIMIT,options,families,popular};
 }
 mark(items,limits,expires,day){
  if(!this.take(limits,expires))return {limited:true};
  const status={};
  for(const it of items){
   if(!this.admitDevice(it.device,it.net,it.now)){status[it.episode+'|'+it.kind]='new-device-limit';continue;}
   const r=this.rows('SELECT start,stop FROM marks WHERE episode=? AND kind=? AND device=?',it.episode,it.kind,it.device)[0];
   if(!r)this.sql.exec('INSERT INTO marks(episode,kind,device,day,start,stop,net) VALUES(?,?,?,?,?,?,?)',it.episode,it.kind,it.device,day,it.start,it.stop,it.net);
   else if(r.start!==it.start||r.stop!==it.stop)this.sql.exec('UPDATE marks SET start=?,stop=?,day=?,net=? WHERE episode=? AND kind=? AND device=?',it.start,it.stop,day,it.net,it.episode,it.kind,it.device);
   status[it.episode+'|'+it.kind]=r?'updated':'stored';
  }
  return {status};
 }
 // Median start/end per chapter and kind; accepted when two or more networks fall within 3 s of both.
 // Each network gives one mark (its most recent); only devices older than MIN_DEVICE_AGE count (S2).
 markStats(now){
  const day=Math.floor(now/DAY);this.sql.exec('DELETE FROM marks WHERE day<?',day-59);const LIMIT=200000;
  const groups=new Map(),out=[],taken=new Set();
  const rows=this.rows("SELECT m.episode AS episode,m.kind AS kind,m.start AS start,m.stop AS stop,m.net AS net FROM marks m JOIN devices d ON d.device=m.device WHERE m.net IS NOT NULL AND m.net<>'' AND d.first<=? ORDER BY m.episode,m.kind,m.day DESC LIMIT ?",now-MIN_DEVICE_AGE,LIMIT+1);
  for(const r of rows.slice(0,LIMIT)){const k=r.episode+'|'+r.kind;if(taken.has(k+'|'+r.net))continue;taken.add(k+'|'+r.net);let g=groups.get(k);if(!g)groups.set(k,g=[]);g.push(r);}
  const median=a=>{const b=[...a].sort((x,y)=>x-y);return b[Math.floor((b.length-1)/2)];};
  for(const [k,g] of groups){
   if(g.length<2)continue;
   const s=median(g.map(r=>r.start)),e=median(g.map(r=>r.stop)),agree=g.filter(r=>Math.abs(r.start-s)<=3&&Math.abs(r.stop-e)<=3);
   if(agree.length>=2){const [episode,kind]=k.split('|');out.push({episode,kind,start:Math.round(agree.reduce((a,r)=>a+r.start,0)/agree.length),stop:Math.round(agree.reduce((a,r)=>a+r.stop,0)/agree.length),devices:agree.length,independentNetworks:agree.length});}
  }
  out.sort((a,b)=>b.devices-a.devices||(a.episode<b.episode?-1:1));
  return {...SIGNAL_POLICY,complete:rows.length<=LIMIT,marks:out.slice(0,5000)};
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
    deadReports:one('SELECT COUNT(*) AS n FROM dead WHERE created>=?',start).n||0,
    plays:one('SELECT COUNT(*) AS n FROM plays WHERE day=?',day).n||0,marks:one('SELECT COUNT(*) AS n FROM marks WHERE day=?',day).n||0},
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
  if(!optionAllowed({name:o?.name,family:f,url:link}))continue;
  const okey=await sha(o.name+'\0'+link);if(!seen.has(okey)){seen.add(okey);out.push({okey,name:o.name,family:f,url:link});}
 }
 return out;
}
function authorized(request,env){return !!env.HELP_KEY&&same(request.headers.get('authorization')||'','Bearer '+env.HELP_KEY);}
export async function handle(request,env,store,deps={}){
 const now=(deps.now||Date.now)(),fetcher=deps.fetch||fetch,url=new URL(request.url),day=Math.floor(now/DAY),expires=(day+2)*DAY;
 const sameAsnZones=Math.max(0,Number(env.SAME_ASN_ZONES||0));
 // 10/11 (app 177): the old workers.dev address is closed; ZZAnime 177+ uses ayuda.zzanime.uk (Cloudflare rate limit).
 // 10/11 (179): old address open again for networks that block the new domain.
 if(request.method==='POST'&&['/v1/submit','/v1/dead','/v1/play','/v1/marks'].includes(url.pathname)){
  // submit: {"schema":1,"device":"<random id>","items":[{"episode":url,"options":[{"name","url"}]}]}; per-item answer:
  // stored | duplicate | enough (drop it, enough devices answered) | stop (not wanted any more) | unsupported.
  // dead:   {"schema":1,"device":"<random id>","items":[{"episode":url,"name","url"}]}; answer per url.
  let x;try{x=await body(request,32768);}catch{return json({accepted:false,reason:'bad-request'},400);}
  if(x?.schema!==1||!/^[A-Za-z0-9_-]{16,64}$/.test(x.device||'')||!Array.isArray(x.items)||!x.items.length||x.items.length>MAX_ITEMS)return json({accepted:false,reason:'bad-request'},400);
  // 10/11 (REVISION-2 N5): the reporter's session (app 176+); required only when REQUIRE_SESSION is "true".
  const user=await sessionUser(request,fetcher,now);if(!user&&env.REQUIRE_SESSION==='true')return json({accepted:false,reason:'login'},401);
  const asn=Number(request.cf?.asn)||0;if(!asn)return json({accepted:false,reason:'no-network'},400);
  const ip=request.headers.get('cf-connecting-ip')||'',device=await sha(env.SALT+'|device|'+x.device),net=await zone(ip,env.SALT);
  const ipKey='ip:'+await sha(env.SALT+'|ip|'+day+'|'+ip),result={},valid=[];
  const acctKey=user?'acct:'+await sha(env.SALT+'|acct|'+day+'|'+user):'';
  const limits=n=>[[ipKey,Number(env.IP_LIMIT||200),1],...(acctKey?[[acctKey,Number(env.ACCOUNT_LIMIT||100),1]]:[]),[(url.pathname==='/v1/dead'?'deadday:':'day:')+day,Number(env.DAILY_CAP||40000),n]];
  if(url.pathname==='/v1/marks'){
   // {"schema":1,"device","items":[{"episode","kind":"intro"|"outro","start":s,"end":s}]}: whole seconds, intro within
   // the first 30 min, each mark at most 4 min long.
   for(const it of x.items){
    const s=it?.start,e=it?.end,ok=EPISODE.test(it?.episode||'')&&['intro','outro'].includes(it?.kind)&&Number.isInteger(s)&&Number.isInteger(e)&&s>=0&&e>s&&e-s<=240&&e<=21600&&(it.kind!=='intro'||s<=1800);
    if(!ok){if(it?.episode)result[String(it.episode).slice(0,300)+'|'+String(it?.kind).slice(0,10)]='unsupported';continue;}
    valid.push({episode:it.episode,kind:it.kind,device,start:s,stop:e,net,now});
   }
   if(valid.length){const r=await store.mark(valid,[[ipKey,Number(env.IP_LIMIT||200),1],['markday:'+day,Number(env.MARK_CAP||10000),valid.length]],expires,day);if(r.limited)return json({accepted:false,reason:'limit'},429);Object.assign(result,r.status);}
   return json({accepted:true,items:Object.entries(result).map(([k,status])=>({episode:k.split('|')[0],kind:k.split('|')[1],status}))});
  }
  if(url.pathname==='/v1/play'){
   // {"schema":1,"device","items":[{"episode","name","url","ok":true|false}]}: played for real or failed for real.
   for(const it of x.items){
    const name=String(it?.name||''),link=String(it?.url||''),f=family(name)||(/^voe\b/i.test(name.trim())?'voe':'');
    if(!EPISODE.test(it?.episode||'')||!f||name.length>70||!LINK.test(link)||link.length>500||typeof it.ok!=='boolean'){if(link)result[link.slice(0,500)]='unsupported';continue;}
    valid.push({okey:await sha(name+'\0'+link),episode:it.episode,name,family:f,url:link,device,ok:it.ok,net,now});
   }
   if(valid.length){const r=await store.play(valid,[[ipKey,Number(env.IP_LIMIT||200),1],['playday:'+day,Number(env.PLAY_CAP||20000),valid.length]],expires,day);if(r.limited)return json({accepted:false,reason:'limit'},429);Object.assign(result,r.status);}
   return json({accepted:true,items:Object.entries(result).map(([u,status])=>({url:u,status}))});
  }
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
   valid.push({episode:it.episode,device,asn,zone:zoneHash,options:opts,...(wanted.get(it.episode).renew?{renew:true}:{})});
  }
  if(valid.length){
   const r=await store.submit(valid,limits(valid.length),expires,now,sameAsnZones);
   if(r.limited){await store.note(day,{limited:1},expires);return json({accepted:false,reason:'limit'},429);}
   Object.assign(result,r.status);const done=[];
   for(const c of r.inspect.slice(0,MAX_INSPECT)){
    // A same-network quorum (asns<2) can only pass on a matching file name: decide() needs 3 networks for quorum3.
    done.push({...c,...await inspect(c,wanted.get(c.episode),fetcher)});
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
 if(request.method==='GET'&&url.pathname==='/v1/renewals'){
  if(!authorized(request,env))return json({error:'unauthorized'},401);
  const wanted=await loadWanted(env,now,fetcher);
  return json({schema:1,generatedAt:iso(now),renewals:await store.renewEvidence([...wanted].filter(([,e])=>e.renew).map(([u])=>u))});
 }
 if(request.method==='GET'&&url.pathname==='/v1/marks-stats'){
  if(!authorized(request,env))return json({error:'unauthorized'},401);
  return json({schema:1,generatedAt:iso(now),...await store.markStats(now)});
 }
 if(request.method==='GET'&&url.pathname==='/v1/play-stats'){
  if(!authorized(request,env))return json({error:'unauthorized'},401);
  return json({schema:1,generatedAt:iso(now),...await store.playStats(now)});
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
