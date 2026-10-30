// ZZAnime help chain (task 10). The signed channel lists the chapters the cloud lacks ("wanted");
// devices answer only those. An option is offered to the cloud only after two devices on two
// different networks (Cloudflare ASN) sent it and its real file name matches the chapter.
// No IP, account or device identifier is stored in clear; everything expires after 8 days.
export const EPISODE=/^https:\/\/jkanime\.net\/[a-zA-Z0-9_-]+\/[1-9][0-9]*\/$/;
const DAY=86400000,KEEP=8*DAY,CHECK_TTL=6*3600000,MAX_OPTIONS=8,MAX_INSPECT=20,WANTED_TTL=120000;
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
 if(payload.schema===1&&age>=-300000&&age<=DAY&&Array.isArray(payload.wanted))for(const w of payload.wanted.slice(0,40))if(EPISODE.test(w.url)&&Number.isInteger(w.number))map.set(w.url,w);
 cached={at:now,map};return map;
}
export function resetWanted(){cached={at:0,map:null};}
// Storage lives in one SQLite-backed Durable Object (free plan); every method is synchronous, so atomic.
export class Store{
 constructor(sql){this.sql=sql;
  sql.exec('CREATE TABLE IF NOT EXISTS submissions(episode TEXT,okey TEXT,name TEXT,family TEXT,url TEXT,device TEXT,asn INTEGER,created INTEGER,PRIMARY KEY(episode,okey,device))');
  sql.exec('CREATE TABLE IF NOT EXISTS counters(k TEXT PRIMARY KEY,n INTEGER,expires INTEGER)');
  sql.exec('CREATE TABLE IF NOT EXISTS checks(okey TEXT PRIMARY KEY,verdict TEXT,detail TEXT,checked INTEGER)');}
 take(limits,expires){
  for(const [k,limit] of limits){const row=this.sql.exec('SELECT n FROM counters WHERE k=?',k).toArray()[0];if(row&&row.n>=limit)return false;}
  for(const [k] of limits)this.sql.exec('INSERT INTO counters(k,n,expires) VALUES(?,1,?) ON CONFLICT(k) DO UPDATE SET n=n+1',k,expires);
  return true;
 }
 add(rows){for(const r of rows)this.sql.exec('INSERT OR IGNORE INTO submissions VALUES(?,?,?,?,?,?,?,?)',r.episode,r.okey,r.name,r.family,r.url,r.device,r.asn,r.created);return rows.length;}
 candidates(since){return this.sql.exec('SELECT episode,okey,name,family,url,COUNT(DISTINCT device) AS devices,COUNT(DISTINCT asn) AS asns,MIN(created) AS first FROM submissions WHERE created>=? GROUP BY episode,okey HAVING devices>=2 AND asns>=2 ORDER BY first LIMIT 400',since).toArray();}
 check(okey,since){return this.sql.exec('SELECT verdict,detail FROM checks WHERE okey=? AND checked>=?',okey,since).toArray()[0]||null;}
 saveCheck(okey,v,now){this.sql.exec('INSERT OR REPLACE INTO checks VALUES(?,?,?,?)',okey,v.verdict,v.detail||'',now);}
 cleanup(now){this.sql.exec('DELETE FROM submissions WHERE created<?',now-KEEP);this.sql.exec('DELETE FROM counters WHERE expires<?',now);this.sql.exec('DELETE FROM checks WHERE checked<?',now-DAY);}
}
async function body(request,limit){const text=await request.text();if(text.length>limit)throw new Error('too large');return JSON.parse(text);}
function same(a,b){if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let d=0;for(let i=0;i<a.length;i++)d|=a.charCodeAt(i)^b.charCodeAt(i);return d===0;}
export async function handle(request,env,store,deps={}){
 const now=(deps.now||Date.now)(),fetcher=deps.fetch||fetch,url=new URL(request.url);
 if(request.method==='POST'&&url.pathname==='/v1/submit'){
  let x;try{x=await body(request,8192);}catch{return json({accepted:false,reason:'bad-request'},400);}
  if(x?.schema!==1||!EPISODE.test(x.episode||'')||!/^[A-Za-z0-9_-]{16,64}$/.test(x.device||'')||!Array.isArray(x.options)||!x.options.length)return json({accepted:false,reason:'bad-request'},400);
  const wanted=await loadWanted(env,now,fetcher);
  // Not asked (or already filled): tell the device to drop it, so nobody keeps working on it.
  if(!wanted.has(x.episode))return json({accepted:false,reason:'not-wanted',stop:true},409);
  const asn=Number(request.cf?.asn)||0;if(!asn)return json({accepted:false,reason:'no-network'},400);
  const day=Math.floor(now/DAY),ip=request.headers.get('cf-connecting-ip')||'';
  if(!await store.take([['ip:'+await sha(env.SALT+'|ip|'+day+'|'+ip),Number(env.IP_LIMIT||60)],['day:'+day,Number(env.DAILY_CAP||5000)]],(day+2)*DAY))return json({accepted:false,reason:'limit'},429);
  const device=await sha(env.SALT+'|device|'+x.device),rows=[],seen=new Set();
  for(const o of x.options.slice(0,MAX_OPTIONS)){
   const f=family(o?.name),link=String(o?.url||'');
   if(!f||typeof o.name!=='string'||o.name.length>70||!/^https:\/\/[a-z0-9.-]+\.[a-z]{2,}\//i.test(link)||link.length>500)continue;
   const okey=await sha(o.name+'\0'+link);if(seen.has(okey))continue;seen.add(okey);
   rows.push({episode:x.episode,okey,name:o.name,family:f,url:link,device,asn,created:now});
  }
  if(!rows.length)return json({accepted:false,reason:'no-supported-option'},422);
  await store.add(rows);return json({accepted:true,stored:rows.length});
 }
 if(request.method==='GET'&&url.pathname==='/v1/accepted'){
  if(!env.HELP_KEY||!same(request.headers.get('authorization')||'','Bearer '+env.HELP_KEY))return json({error:'unauthorized'},401);
  await store.cleanup(now);const wanted=await loadWanted(env,now,fetcher),out=new Map();let inspected=0;
  for(const c of await store.candidates(now-KEEP)){
   const entry=wanted.get(c.episode);if(!entry)continue;
   const ck=c.episode+'|'+c.okey;let v=await store.check(ck,now-CHECK_TTL);
   if(!v){if(inspected>=MAX_INSPECT)continue;inspected++;v=await inspect(c,entry,fetcher);await store.saveCheck(ck,v,now);}
   const check=v.verdict==='match'?'name-match':v.verdict==='unknown'&&c.family!=='mega'&&c.asns>=3?'quorum3':null;
   if(!check)continue;
   const row=out.get(c.episode)||{url:c.episode,acceptedAt:iso(c.first),...(entry.firstSeenAt?{firstSeenAt:entry.firstSeenAt}:{}),options:[]};
   if(c.first<Date.parse(row.acceptedAt))row.acceptedAt=iso(c.first);
   row.options.push({name:c.name,family:c.family,url:c.url,devices:c.devices,asns:c.asns,check});out.set(c.episode,row);
  }
  return json({schema:1,generatedAt:iso(now),episodes:[...out.values()]});
 }
 if(request.method==='GET'&&url.pathname==='/')return new Response('ZZAnime ayuda entre dispositivos.',{headers:{'content-type':'text/plain; charset=utf-8'}});
 return json({error:'not-found'},404);
}
