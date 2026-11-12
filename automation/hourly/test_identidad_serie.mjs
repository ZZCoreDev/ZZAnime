// 12/11 décima revisión R10-01: the main, voe/ and extra/ files of one series have DIFFERENT names (content hashes) and a
// new publication renames them again; they must count as ONE series. Real channel + Quota (SQLite in memory).
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {createHash} from 'node:crypto';
import {handle,resetKeys,resetSeriesMaps} from './channel_gate.mjs';
import {Quota,forgetBans,quizTarget} from './quota.mjs';
import {publication} from './test_publicacion.mjs';
const ISS='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',sha=t=>createHash('sha256').update(t).digest('hex');
const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']),jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
const b64=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
async function token(c){const h=b64(JSON.stringify({alg:'ES256',kid:'k1'})),p=b64(JSON.stringify(c));return h+'.'+p+'.'+b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,new TextEncoder().encode(h+'.'+p)));}
const db=new DatabaseSync(':memory:'),obj=new Quota({storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}});
let cdata='';const net=async url=>{const u=String(url);if(u.includes('siteverify')){await obj.fetch(new Request('https://quota/hmark?n='+cdata));return new Response(JSON.stringify({success:true,hostname:'zzanime.uk',action:'enlaces',cdata}));}
 if(u.includes('zz_editor_access'))return new Response('{"allowed":false,"aal2":false}');return new Response(JSON.stringify({keys:[{...jwk,alg:'ES256',kid:'k1'}]}));};
const pub=publication(),env={ASSETS:pub,REQUIRE_SESSION:'true',LINK_RULES:'enforce',QUOTA_MODE:'enforce',TURNSTILE_SECRET:'s',QUOTA:{idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})}};
resetKeys();forgetBans();resetSeriesMaps();
const tk=await token({iss:ISS,role:'authenticated',aud:'authenticated',sub:'identidad',exp:Math.floor(Date.now()/1000)+600});
const file=(serie,kind,v='')=>'series/'+sha(serie+kind+v)+'.bin';
const publish=(serie,v='')=>{for(const [prefix,kind] of [['','m'],['voe/','v'],['extra/','e']])pub.add(prefix,file(serie,kind,v),pub.key(serie));};
const get=(prefix,f,human)=>handle(new Request('https://respaldo.zzanime.uk/'+prefix+f,{headers:{Authorization:'Bearer '+tk,...(human?{'X-ZZ-Human':'tok-1234567890:q'+quizTarget(cdata)}:{})}}),env,net);
const all=async serie=>[(await get('',file(serie,'m'))).status,(await get('voe/',file(serie,'v'))).status,(await get('extra/',file(serie,'e'))).status];
for(const s of 'ABCDEFG')publish(s);
// three complete series (3 files each, all different names) are free; the 4th asks
for(const s of 'ABC')assert.deepEqual(await all(s),[200,200,200],'series '+s+' (main+voe+extra) counts once');
let r=await get('extra/',file('D','e'));assert.equal(r.status,428,'4th series asks, also from extra/');
// the challenge of any of its files is valid for the whole series: extra's challenge opens main, then voe/extra are free
cdata=(await r.json()).challenge;assert.equal((await get('',file('D','m'),true)).status,200);
assert.deepEqual(await all('D'),[200,200,200]);
// 12/11 (más estricta): one check = that series only; E asks again
assert.equal((await get('voe/',file('E','v'))).status,428,'E asks again');
// a series opened on an earlier day (within 30 days) reopens free and is not counted again
const ago=d=>new Date(Date.now()-d*86400000).toISOString().slice(0,10);
db.prepare('insert into seen(day,user,item,at) values(?,?,?,?)').run(ago(20),'u:identidad','s:'+pub.key('G'),Date.now()-20*86400000);
assert.deepEqual(await all('G'),[200,200,200],'opened 20 days ago: free');
db.prepare('insert into seen(day,user,item,at) values(?,?,?,?)').run(ago(40),'u:identidad','s:'+pub.key('F'),Date.now()-40*86400000);
assert.equal((await get('',file('F','m'))).status,428,'opened 40 days ago: counts as new');
// a new publication of A (new file names) is the same series: free
for(const [prefix,kind] of [['','m'],['voe/','v'],['extra/','e']])pub.remove(prefix,file('A',kind));publish('A','2');
assert.equal((await get('',file('A','m','2'))).status,200,'revision of a series already opened: free');
assert.equal((await get('',file('A','m'))).status,404,'old file not in the current index: 404, never served uncounted');
// a file that is not in any index is 404 and is not counted
assert.equal((await get('',file('Z','m'))).status,404);
console.log('identidad de serie (R10-01): main/voe/extra con nombres distintos y revisiones cuentan 1; fuera del índice 404; reabrir en 30 días gratis OK');
