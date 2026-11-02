// S2 attack controls: invented device ids from one network never add votes, marks or popularity.
// No network: every provider, MEGA and channel request goes to local fakes.
import assert from 'node:assert/strict';
import {createCipheriv,generateKeyPairSync,randomBytes,sign} from 'node:crypto';
// node:sqlite needs Node >= 22.5; GitHub's ubuntu-24.04 default Node is older, so skip instead of breaking the chain.
let DatabaseSync;
try{({DatabaseSync}=await import('node:sqlite'));}catch{console.log('help Worker controls SKIPPED: node:sqlite needs Node >= 22.5 (found '+process.version+')');process.exit(0);}
import {handle,Store,family,nameVerdict,megaName,resetWanted,sha} from './logic.js';

const TR='https://jkanime.net/tokyo-revengers-santen-sensou-hen/5/',SBR='https://jkanime.net/steel-ball-run-jojo-no-kimyou-na-bouken/7/',OLD='https://jkanime.net/ao-ashi/3/';
const WANTED=[{url:TR,number:5,title:'Tokyo Revengers: Santen Sensou-hen'},{url:SBR,number:7,title:'Steel Ball Run: JoJo no Kimyou na Bouken'},{url:OLD,number:3,title:'Ao Ashi',renew:true}];
const {publicKey,privateKey}=generateKeyPairSync('rsa',{modulusLength:2048});
const b64u=b=>Buffer.from(b).toString('base64').replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
function sqlite(){const db=new DatabaseSync(':memory:');return {exec(q,...p){const s=db.prepare(q);if(/^\s*SELECT/i.test(q))return {toArray:()=>s.all(...p).map(r=>({...r}))};s.run(...p);return {toArray:()=>[]};}};}
function channel(wanted,createdAt){const payload=JSON.stringify({schema:1,sequence:1,createdAt,indexSha256:'0'.repeat(64),indexPath:'indexes/'+'0'.repeat(64)+'.bin',indexBytes:1,mode:'daily-new',...(wanted?{wanted}:{})});return JSON.stringify({payload,signature:sign('sha256',Buffer.from(payload),privateKey).toString('hex')});}
function megaFile(name,id='AbCd1234'){
 const k=randomBytes(32),aes=Buffer.alloc(16);for(let i=0;i<16;i++)aes[i]=k[i]^k[i+16];
 let plain=Buffer.from('MEGA'+JSON.stringify({n:name}));plain=Buffer.concat([plain,Buffer.alloc((16-plain.length%16)%16)]);
 const c=createCipheriv('aes-128-cbc',aes,Buffer.alloc(16));c.setAutoPadding(false);
 return {id,key:b64u(k),at:b64u(Buffer.concat([c.update(plain),c.final()])),url:'https://mega.nz/file/'+id+'#'+b64u(k)};
}
function setup({wanted=WANTED,age=60000,mega=[],pages={}}={}){
 const now=Date.parse('2026-10-31T00:00:00Z');resetWanted();
 const env={PUBLIC_KEY:publicKey.export({type:'spki',format:'der'}).toString('base64'),CHANNEL_URL:'https://channel.test/channel.json',SALT:'salt',HELP_KEY:'secret',IP_LIMIT:'3',DAILY_CAP:'1000'};
 const files=Object.fromEntries(mega.map(f=>[f.id,f.at]));
 const fetcher=async(url,init={})=>{
  if(url===env.CHANNEL_URL)return new Response(channel(wanted,new Date(now-age).toISOString()));
  if(url.startsWith('https://g.api.mega.co.nz/cs')){const id=JSON.parse(init.body)[0].p;return Response.json(files[id]?[{s:1,at:files[id]}]:[-9]);}
  if(pages[url])return new Response('<html><title>'+pages[url]+'</title></html>');
  return new Response('blocked',{status:403});};
 return {now,env,store:new Store(sqlite()),fetcher};
}
let n=0;
async function submit(t,items,{device,asn=3352,ip}={}){
 device=device||'device-'+String(++n).padStart(12,'0');
 const req=new Request('https://help.test/v1/submit',{method:'POST',body:JSON.stringify({schema:1,device,items})});
 Object.defineProperty(req,'cf',{value:{asn}});req.headers.set('cf-connecting-ip',ip||device);
 const r=await handle(req,t.env,t.store,{now:()=>t.now,fetch:t.fetcher});const body=await r.json();
 return {status:r.status,body,of:e=>body.items?.find(i=>i.episode===e)?.status};
}
const item=(episode,...urls)=>({episode,options:urls.map(u=>({name:u.includes('mega')?'Mega':u.includes('vidhide')?'Vidhide':u.includes('mp4upload')?'Mp4upload':'Streamwish',url:u}))});
async function accepted(t,key='secret'){const r=await handle(new Request('https://help.test/v1/accepted',{headers:{authorization:'Bearer '+key}}),t.env,t.store,{now:()=>t.now+1000,fetch:t.fetcher});return {status:r.status,body:await r.json()};}
let passed=0;const check=async(name,fn)=>{await fn();passed++;};

async function get(t,path,key='secret'){const r=await handle(new Request('https://help.test'+path,{headers:{authorization:'Bearer '+key}}),t.env,t.store,{now:()=>t.now+1000,fetch:t.fetcher});return {status:r.status,body:await r.json()};}
// S2: each test device sits on its own /24 network unless the test says otherwise.
const nets=new Map(),netFor=d=>{if(!nets.has(d))nets.set(d,'10.'+(nets.size+1)+'.0.1');return nets.get(d);};
const MATURE=25*3600000;
async function play(t,items,{device,asn=3352,ip}={}){
 device=device||'device-'+String(++n).padStart(12,'0');
 const req=new Request('https://help.test/v1/play',{method:'POST',body:JSON.stringify({schema:1,device,items})});
 Object.defineProperty(req,'cf',{value:{asn}});req.headers.set('cf-connecting-ip',ip||netFor(device));
 const r=await handle(req,t.env,t.store,{now:()=>t.now,fetch:t.fetcher});const body=await r.json();return {status:r.status,body,of:u=>body.items?.find(i=>i.url===u)?.status};
}
async function mark(t,items,{device,asn=3352,ip}={}){
 device=device||'device-'+String(++n).padStart(12,'0');
 const req=new Request('https://help.test/v1/marks',{method:'POST',body:JSON.stringify({schema:1,device,items})});
 Object.defineProperty(req,'cf',{value:{asn}});req.headers.set('cf-connecting-ip',ip||netFor(device));
 const r=await handle(req,t.env,t.store,{now:()=>t.now,fetch:t.fetcher});return {status:r.status,body:await r.json()};
}
const p=(u,ok=true,e=TR)=>({episode:e,name:'Mp4upload',url:u,ok});
const m=(start,end)=>({episode:TR,kind:'intro',start,end});
await check('three invented ids on one network are one voter; an option needs three networks',async()=>{
 const t=setup(),u='https://www.mp4upload.com/embed-fake1234.html';
 for(const d of ['device-fake-device-1','device-fake-device-2','device-fake-device-3'])await play(t,[p(u)],{device:d,ip:'81.2.3.4'});
 t.now+=MATURE;const st=(await get(t,'/v1/play-stats')).body;
 assert.deepEqual(st.options,[]);assert.deepEqual(st.popular,[]);assert.deepEqual(st.families.mp4upload,[1,0]);});
await check('two invented ids on one network cannot agree an intro mark; two networks can',async()=>{
 const t=setup();
 await mark(t,[m(500,740)],{device:'device-mark-fake-001',ip:'81.2.3.4'});await mark(t,[m(500,740)],{device:'device-mark-fake-002',ip:'81.2.3.9'});
 t.now+=MATURE;assert.deepEqual((await get(t,'/v1/marks-stats')).body.marks,[]);
 await mark(t,[m(500,740)],{device:'device-mark-real-003',ip:'90.1.1.1'});t.now+=MATURE;
 assert.deepEqual((await get(t,'/v1/marks-stats')).body.marks.map(x=>x.independentNetworks),[2]);});
await check('devices younger than 24 h do not count yet',async()=>{
 const t=setup(),u='https://www.mp4upload.com/embed-young123.html';
 for(const ip of ['82.1.1.1','82.2.1.1','82.3.1.1'])await play(t,[p(u)],{ip});
 assert.deepEqual((await get(t,'/v1/play-stats')).body.options,[]);
 t.now+=MATURE;assert.deepEqual((await get(t,'/v1/play-stats')).body.options.map(o=>o.independentNetworks),[3]);});
await check('a network can introduce at most five new devices a day; known devices keep working',async()=>{
 const t=setup(),u='https://www.mp4upload.com/embed-flood123.html',res=[];
 for(let i=1;i<=6;i++)res.push((await play(t,[p(u)],{device:'device-flood-devic-'+i,ip:'83.1.1.'+i})).of(u));
 assert.deepEqual(res,['stored','stored','stored','stored','stored','new-device-limit']);
 const v='https://www.mp4upload.com/embed-known123.html';assert.equal((await play(t,[p(v)],{device:'device-flood-devic-1',ip:'83.1.1.1'})).of(v),'stored');});
await check('requests without a usable network address count nothing',async()=>{
 const t=setup(),u='https://www.mp4upload.com/embed-noaddr12.html';
 assert.equal((await play(t,[p(u)],{ip:'not-an-ip'})).of(u),'new-device-limit');});
await check('summaries carry the evidence policy the cloud requires',async()=>{
 const t=setup();const a=(await get(t,'/v1/play-stats')).body,b=(await get(t,'/v1/marks-stats')).body;
 for(const x of [a,b]){assert.equal(x.evidencePolicy,'network-v2');assert.equal(x.basis,'independent-networks');assert.equal(x.minDeviceAgeHours,24);assert.equal(x.complete,true);assert.ok(x.generatedAt);}});
await check('every store method the handler calls is exposed by the Durable Object wrapper',async()=>{
 const fs=await import('node:fs');const logic=fs.readFileSync(new URL('./logic.js',import.meta.url),'utf8'),worker=fs.readFileSync(new URL('./worker.js',import.meta.url),'utf8');
 const handler=logic.slice(logic.indexOf('export async function handle('));const used=[...new Set([...handler.matchAll(/store\.([a-zA-Z]+)\(/g)].map(m=>m[1]))];
 assert.ok(used.length>5);for(const m of used)assert.ok(worker.includes('\n '+m+'('),'worker.js must expose '+m);});
console.log(passed+' S2 signal controls PASS (one network = one voter, 24 h device age, 5 new devices per network and day, attested summaries)');
