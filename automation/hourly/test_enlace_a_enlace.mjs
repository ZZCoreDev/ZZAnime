// 17/11/2026 (Robin): «enlace a enlace». Attack tests on the real channel gate + real Quota (SQLite in memory): nobody gets
// addresses without a session, without the counter, or by reusing someone else's / another link's check; whoever opens
// nearly all the servers of 4 series must pass «soy humano» on EVERY new server; reopening is free; caps hold across accounts.
import assert from 'node:assert/strict';
import {gzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {handle,resetKeys,resetDoor} from './channel_gate.mjs';
import {Quota,forgetBans,quizTarget} from './quota.mjs';
const ISS='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1';
const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']),jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
const b64=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
async function token(c){const h=b64(JSON.stringify({alg:'ES256',kid:'k1'})),p=b64(JSON.stringify(c));return h+'.'+p+'.'+b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,new TextEncoder().encode(h+'.'+p)));}
const sha=t=>createHash('sha256').update(t).digest('hex');
let db;function quota(){db=new DatabaseSync(':memory:');const state={storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}};
 const obj=new Quota(state);return {idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};}
// publication: 8 series of 4 chapters x 3 servers (12 links each) in the main channel, one in latino/
const files=new Map(),index={'':{},'latino/':{}};
const series=n=>'https://jkanime.net/serie-'+n+'/',link=(n,c,v)=>'https://voe.sx/e/s'+n+'c'+c+'v'+v+'abcdef';
function publish(prefix,n){const row={schema:1,series:series(n),episodes:[1,2,3,4].map(c=>({url:series(n)+c+'/',options:[0,1,2].map(v=>({family:'voe',name:'VOE',url:link(n,c,v),...(prefix?{lang:'es-LA'}:{})}))}))};
 const packed=gzipSync(Buffer.from(JSON.stringify(row))),path='series/'+sha(packed)+'.bin';files.set(prefix+path,packed);index[prefix][sha(series(n))]={path};}
for(let n=1;n<=8;n++)publish('',n);publish('latino/',9);
const assets={fetch(r){const p=new URL(r.url).pathname.slice(1),m=/^(latino\/)?(.*)$/.exec(p),prefix=m[1]||'',rest=m[2];
 if(rest==='channel.json')return new Response(JSON.stringify({payload:JSON.stringify({schema:1,indexPath:'indexes/'+'a'.repeat(64)+'.bin'})}));
 if(rest==='indexes/'+'a'.repeat(64)+'.bin')return new Response(JSON.stringify({schema:1,series:index[prefix]}));
 if(files.has(p))return new Response(files.get(p));return new Response('nf',{status:404});}};
let cdata='';const ownerTk='o'.repeat(40);
const net=async(url,init)=>{const u=String(url);
 if(u.includes('siteverify')){await env.QUOTA.get('global').fetch('https://quota/hmark?n='+cdata);return new Response(JSON.stringify({success:true,hostname:'zzanime.uk',action:'enlaces',cdata}));}
 if(u.includes('zz_editor_access'))return new Response(init?.headers?.Authorization==='Bearer '+ownerTk?'{"allowed":true,"aal2":true}':'{"allowed":false,"aal2":false}');
 return new Response(JSON.stringify({keys:[{...jwk,alg:'ES256',kid:'k1'}]}));};
const env={ASSETS:assets,REQUIRE_SESSION:'true',LINK_RULES:'enforce',QUOTA_MODE:'enforce',TURNSTILE_SECRET:'s',LINK_DOOR:'on',QUOTA:quota(),CLOUD_KEY:'cloud-secret-123'};
resetKeys();forgetBans();resetDoor();
const user=sub=>token({iss:ISS,role:'authenticated',aud:'authenticated',sub,exp:Math.floor(Date.now()/1000)+600});
const key=(n,c,v)=>sha('voe\0'+link(n,c,v));
const setting=async(o)=>{for(const [name,value] of Object.entries(o)){const r=await env.QUOTA.get('global').fetch('https://quota/admin/set?name='+name+'&value='+value);if(r.status!==200)throw Error('set '+name+' '+r.status);}};
const q=(o)=>'?'+new URLSearchParams(o).toString();
const call=(tk,path,{human=false,ip='203.0.113.7',env:e=env,auth}={})=>handle(new Request('https://respaldo.zzanime.uk'+path,{headers:{...(tk?{Authorization:'Bearer '+tk}:{}),...(auth?{Authorization:auth}:{}),'CF-Connecting-IP':ip,...(human?{'X-ZZ-Human':'tok-1234567890:q'+quizTarget(cdata)}:{})}}),e,net);
const one=(tk,n,c,v,opts)=>call(tk,'/enlace'+q({p:'',s:sha(series(n)),e:series(n)+c+'/',k:key(n,c,v)}),opts);
const tk=await user('robin-ataque');
// 1) off by default, closed without session, strict parameters
assert.equal((await one(tk,1,1,0,{env:{...env,LINK_DOOR:undefined}})).status,404,'off');
assert.equal((await one(null,1,1,0)).status,401,'no session');
const anon=await token({iss:ISS,role:'authenticated',aud:'authenticated',sub:'anon1',is_anonymous:true,exp:Math.floor(Date.now()/1000)+600});
assert.equal((await one(anon,1,1,0)).status,401,'anonymous');
for(const bad of [{p:'',s:sha(series(1)),e:series(1)+'1/',k:key(1,1,0),x:'1'},{p:'otro',s:sha(series(1)),e:series(1)+'1/',k:key(1,1,0)},{p:'',s:'zz',e:series(1)+'1/',k:key(1,1,0)},
 {p:'',s:sha(series(1)),e:'https://evil.example/a/1/',k:key(1,1,0)},{p:'',s:sha(series(1)),e:series(1)+'1/',k:'nope'},{p:'',s:sha(series(1)),e:series(1)+'1/'}])
 assert.equal((await call(tk,'/enlace'+q(bad))).status,400,JSON.stringify(bad));
assert.equal((await call(tk,'/opciones'+q({p:'',s:sha(series(1)),e:series(1)+'1/',k:key(1,1,0)}))).status,400,'opciones never takes a key');
// 2) /opciones lists servers WITHOUT addresses
{const r=await call(tk,'/opciones'+q({p:'',s:sha(series(1)),e:series(1)+'1/'}));assert.equal(r.status,200);const text=await r.text();
 assert.ok(!text.includes('voe.sx')&&!text.includes('"url"'),'no address in the list');assert.equal(JSON.parse(text).options.length,3);assert.equal(JSON.parse(text).options[0].key,key(1,1,0));}
{const r=await call(tk,'/opciones'+q({s:sha(series(9)),e:series(9)+'1/'}));assert.equal(r.status,200);const x=await r.json();assert.ok(x.options.every(o=>o.p==='latino'&&!('url' in o)),'merged list, latino only for serie 9');
 assert.equal((await call(tk,'/enlace'+q({s:sha(series(1)),e:series(1)+'1/',k:key(1,1,0)}))).status,400,'enlace needs p');}
// 3) unknown series / chapter / server: 404 and NOT counted
assert.equal((await call(tk,'/enlace'+q({p:'',s:sha('https://jkanime.net/no/'),e:'https://jkanime.net/no/1/',k:key(1,1,0)}))).status,404);
assert.equal((await call(tk,'/enlace'+q({p:'',s:sha(series(1)),e:series(1)+'9/',k:key(1,1,0)}))).status,404);
assert.equal((await call(tk,'/enlace'+q({p:'',s:sha(series(1)),e:series(1)+'1/',k:key(2,1,0)}))).status,404,'a key of another series does not open here');
assert.equal(db.prepare('select count(*) c from lseen').get().c,0,'nothing counted for junk');
// 4) a normal viewer: one server per chapter, never asked
{const r=await one(tk,1,1,0);assert.equal(r.status,200);const x=await r.json();assert.equal(x.url,link(1,1,0));assert.equal(r.headers.get('Cache-Control'),'private, no-store');}
for(const c of [2,3,4])assert.equal((await one(tk,1,c,0)).status,200,'normal viewing');
await setting({lburst:1000,lsoft:1000}); // only the 4-series rule here
// 5) a thief: nearly all (≥75 %, ≥8) of the servers of 4 series ...
for(const n of [1,2,3,4])for(const c of [1,2,3])for(const v of [0,1,2]){const r=await one(tk,n,c,v);if(r.status!==200)assert.fail('setup '+n+c+v+' '+r.status);}
assert.equal(db.prepare("select count(*) c from lfull where user='u:robin-ataque'").get().c,4,'4 series nearly fully opened');
// ... then EVERY new server asks «soy humano»
let r=await one(tk,5,1,0);assert.equal(r.status,428,'new server asks');cdata=(await r.json()).challenge;
assert.equal((await one(tk,5,1,1,{human:true})).status,428,'the check of server A does not open server B');
assert.equal((await one(tk,5,1,0,{human:true})).status,200,'checked: only that server opens');
assert.equal((await one(tk,5,1,0,{human:true})).status,200,'reopening the same server is free');
r=await one(tk,5,1,1);assert.equal(r.status,428,'next new server asks again');
assert.equal((await one(tk,5,1,1,{human:true})).status,428,'an already used check does not open another');
// reopening anything already opened stays free, and the check is per account
for(const [n,c,v] of [[1,1,0],[2,3,1],[4,3,2]])assert.equal((await one(tk,n,c,v)).status,200,'reopen free');
{const other=await user('otra-cuenta');r=await one(tk,6,1,0);const mine=(await r.json()).challenge;cdata=mine;
 assert.equal((await one(other,6,1,0,{human:true})).status,200,'other account: under its own limits, not using mine');
 assert.equal(db.prepare('select count(*) c from challenges where nonce=?').get(mine).c,1,'my challenge was not spent by the other account');}
// 6) the editor owner with authenticator is never asked
assert.equal((await call(null,'/enlace'+q({p:'',s:sha(series(7)),e:series(7)+'1/',k:key(7,1,0)}),{auth:'Bearer '+tk})).status,428);
{const ownerJwt=await user('dueno');const ownerReq=new Request('https://respaldo.zzanime.uk/enlace'+q({p:'',s:sha(series(7)),e:series(7)+'1/',k:key(7,1,0)}),{headers:{Authorization:'Bearer '+ownerJwt}});
 // the owner check asks Supabase with the same bearer; here only the owner token passes it
 const ownerNet=async(url,init)=>String(url).includes('zz_editor_access')?new Response('{"allowed":true,"aal2":true}'):net(url,init);
 db.prepare("insert into lfull(day,user,series) values(?,?,?),(?,?,?),(?,?,?),(?,?,?)").run(...[1,2,3,4].flatMap(n=>[new Date().toISOString().slice(0,10),'u:dueno',sha(series(n))]));
 assert.equal((await handle(ownerReq,env,ownerNet)).status,200,'owner not asked');}
env.QUOTA=quota();
// 7) bursts: 15 new servers in 10 minutes ask the check, even in one series
{const b=await user('rafaga');let asked=false;for(const n of [1,2])for(const c of [1,2,3,4])for(const v of [0,1,2]){const x=await one(b,n,c,v,{ip:'198.51.100.'+(n*10+c)});if(x.status===428){asked=true;break;}}assert.ok(asked,'burst asks');}
// 8) many accounts behind one connection: the network cap stops them
{env.QUOTA=quota();await setting({lipcap:20});
 let blocked=false;for(let a=0;a<6&&!blocked;a++){const t=await user('granja-'+a);for(const c of [1,2,3,4]){const x=await one(t,8,c,a%3,{ip:'192.0.2.50'});if(x.status===429){blocked=true;break;}}
  for(const c of [1,2,3,4]){const x=await one(t,7,c,a%3,{ip:'192.0.2.50'});if(x.status===429){blocked=true;break;}}}
 assert.ok(blocked,'network cap across accounts');}
// 8b) many accounts behind one connection, each under its own limits: past lipsoft links from that network, EVERY new
// link asks the check, for every account there (17/11 revisión)
{env.QUOTA=quota();await setting({lipsoft:12,lipcap:1000});let first428=-1,i=0;
 for(let a=0;a<6;a++){const t=await user('red-'+a);for(const c of [1,2,3,4]){const x=await one(t,1+a,c,a%3,{ip:'192.0.2.77'});if(x.status===428&&first428<0)first428=i;i++;}}
 assert.ok(first428>=12&&first428<=13,'asks right after 12 links from the same connection: '+first428);
 const other=await user('otra-red');assert.equal((await one(other,1,1,0,{ip:'198.51.100.200'})).status,200,'another connection is not affected');}
// 9) hard daily cap per account
{env.QUOTA=quota();await setting({lcap:5,lsoft:0,lfull:100,lburst:1000});const t=await user('tope');let codes=[];
 for(const c of [1,2,3,4])for(const v of [0,1])codes.push((await one(t,1,c,v)).status);assert.deepEqual(codes,[200,200,200,200,200,429,429,429],'cap');}
// 10) latino/ through the same door
{env.QUOTA=quota();const t=await user('latino');r=await call(t,'/enlace'+q({p:'latino',s:sha(series(9)),e:series(9)+'2/',k:key(9,2,1)}));assert.equal(r.status,200);assert.equal((await r.json()).lang,'es-LA');}
// 11) old whole-series files can be closed for apps; the cloud key still reads them
assert.equal((await call(tk,'/series/'+'b'.repeat(64)+'.bin',{env:{...env,LEGACY_SERIES:'closed'}})).status,410,'closed for apps');
assert.equal((await handle(new Request('https://respaldo.zzanime.uk/series/x.bin',{headers:{'X-ZZ-Cloud':'cloud-secret-123'}}),{...env,LEGACY_SERIES:'closed'},net)).status,404,'cloud key passes the door (file itself unknown here)');
// 12) counter down: closed, never served without counting
{const down={idFromName:()=>1,get:()=>({fetch:async()=>{throw Error('down')}})};assert.equal((await one(tk,3,1,0,{env:{...env,QUOTA:down}})).status,503);}
// 13) with a session, only the exact file shapes: encoded letters, double slashes or other files never reach a series file uncounted
{const sneaky=['/%73eries/'+'a'.repeat(64)+'.bin','//series/'+'a'.repeat(64)+'.bin','/series//'+'a'.repeat(64)+'.bin','/Series/'+'a'.repeat(64)+'.bin','/series/'+'a'.repeat(64)+'.bin%00','/voe/%73eries/x.bin','/robots.txt','/index.html','/series/'+'a'.repeat(64)+'.json'];
 for(const p of sneaky){const r=await handle(new Request('https://respaldo.zzanime.uk'+p,{headers:{Authorization:'Bearer '+tk}}),env,net);assert.equal(r.status,404,p);}}
console.log('enlace a enlace OK');
