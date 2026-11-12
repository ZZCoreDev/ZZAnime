// 12/11 (Robin): nobody copies more than 3 series with all their links without being stopped. Real channel + real Quota
// (SQLite in memory), LINK_RULES enforce with the DEFAULT limits: 3 new series a day free, then EVERY new series asks (12/11),
// voe/extra count as the same series, reopening is free, daily cap 30 (9 for new accounts).
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {handle,resetKeys} from './channel_gate.mjs';
import {Quota,forgetBans,quizTarget} from './quota.mjs';
const ISS='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1';
const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']),jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
const b64=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
async function token(c){const h=b64(JSON.stringify({alg:'ES256',kid:'k1'})),p=b64(JSON.stringify(c));return h+'.'+p+'.'+b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,new TextEncoder().encode(h+'.'+p)));}
function quota(){const db=new DatabaseSync(':memory:'),state={storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}};
 const obj=new Quota(state);return {idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};}
let cdata='';const net=async(url,init)=>{const u=String(url);if(u.includes('siteverify')){await env.QUOTA.get('global').fetch('https://quota/hmark?n='+cdata);return new Response(JSON.stringify({success:true,hostname:'zzanime.uk',action:'enlaces',cdata}));}
 if(u.includes('zz_editor_access'))return new Response('{"allowed":false,"aal2":false}');return new Response(JSON.stringify({keys:[{...jwk,alg:'ES256',kid:'k1'}]}));};
const pub=(await import('./test_publicacion.mjs')).publication(),reg=p=>{const m=/^\/((?:voe|extra)\/)?(series\/([^/]+)\.bin)$/.exec(p);if(m)pub.add(m[1]||'',m[2],pub.key(m[3]));return p;};
const env={ASSETS:pub,REQUIRE_SESSION:'true',LINK_RULES:'enforce',QUOTA_MODE:'enforce',TURNSTILE_SECRET:'s',QUOTA:quota()};
resetKeys();forgetBans();
const user=async(sub,fresh=false)=>token({iss:ISS,role:'authenticated',aud:'authenticated',sub,exp:Math.floor(Date.now()/1000)+600,...(fresh?{zz_new:true}:{})});
const s=c=>c.repeat(64).slice(0,64);
const open=async(tk,path,human)=>handle(new Request('https://respaldo.zzanime.uk'+reg(path),{headers:{Authorization:'Bearer '+tk,...(human?{'X-ZZ-Human':'tok-1234567890:q'+(/^[a-f0-9]{32}$/.test(cdata)?quizTarget(cdata):0)}:{})}}),env,net);
const tk=await user('robin-test');
// 3 new series free
for(const c of 'abc')assert.equal((await open(tk,'/series/'+s(c)+'.bin')).status,200,'free '+c);
// voe/extra of an opened series: same series, free
assert.equal((await open(tk,'/voe/series/'+s('a')+'.bin')).status,200);assert.equal((await open(tk,'/extra/series/'+s('b')+'.bin')).status,200);
// the 4th new series asks the box (also when it comes through voe/ or extra/)
let r=await open(tk,'/extra/series/'+s('d')+'.bin');assert.equal(r.status,428,'4th series via extra/ asks');
r=await open(tk,'/series/'+s('d')+'.bin');assert.equal(r.status,428);const {challenge}=await r.json();
cdata=challenge;assert.equal((await open(tk,'/series/'+s('d')+'.bin',true)).status,200,'ticked: d opens');
// 12/11 (más estricta): the tick unlocks only d; its voe/extra are free, the next new series (e) asks again
assert.equal((await open(tk,'/voe/series/'+s('d')+'.bin')).status,200,'voe of d: same series');
r=await open(tk,'/series/'+s('e')+'.bin');assert.equal(r.status,428,'e asks again');cdata=(await r.json()).challenge;
assert.equal((await open(tk,'/series/'+s('e')+'.bin',true)).status,200,'ticked: e opens');
assert.equal((await open(tk,'/voe/series/'+s('f')+'.bin')).status,428,'f asks again (also via voe/)');
// a challenge is bound to its own series: e's used challenge does not open f
assert.equal((await open(tk,'/series/'+s('f')+'.bin',true)).status,428,'old challenge does not open another series');
// reopening any opened series stays free
for(const c of 'abcde')assert.equal((await open(tk,'/series/'+s(c)+'.bin')).status,200,'reopen '+c);
// a whole catalogue in one go is impossible: 30 a day at most even ticking every time
{const t2=await user('copier');let opened=0,boxes=0;for(let i=0;i<60;i++){const name=(i.toString(16)+'z').repeat(64).slice(0,64);let x=await open(t2,'/series/'+name+'.bin');
  if(x.status===428){boxes++;cdata=(await x.json()).challenge;x=await open(t2,'/series/'+name+'.bin',true);}if(x.status===200)opened++;else break;}
 assert.equal(opened,30,'daily cap 30');assert.equal(boxes,27,'a box for every new series after the 3rd: '+boxes);}
// new accounts: 9 a day
{const t3=await user('nueva',true);let opened=0;for(let i=0;i<20;i++){const name=('n'+i.toString(16)).repeat(64).slice(0,64);let x=await open(t3,'/series/'+name+'.bin');
  if(x.status===428){cdata=(await x.json()).challenge;x=await open(t3,'/series/'+name+'.bin',true);}if(x.status===200)opened++;else break;}
 assert.equal(opened,9,'new account cap 9');}
// 12/11: the picture question after the box: right answer opens, wrong answer does not.
{const t4=await user('quiz');for(const c of '123')await open(t4,'/series/'+('q'+c).repeat(32)+'.bin');
 const ask=async(name,ans)=>{const r=await open(t4,'/series/'+name+'.bin');assert.equal(r.status,428);cdata=(await r.json()).challenge;
  return handle(new Request('https://respaldo.zzanime.uk'+reg('/series/'+name+'.bin'),{headers:{Authorization:'Bearer '+t4,'X-ZZ-Human':'tok-1234567890:q'+ans(cdata)}}),env,net);};
 assert.equal((await ask('w'.repeat(64),c=>(quizTarget(c)+1)%6)).status,428,'wrong picture: still asks');
 assert.equal((await ask('x'.repeat(64),c=>quizTarget(c))).status,200,'right picture: opens');}
console.log('soy humano estricto: 3 libres, luego casilla en CADA serie nueva, voe/extra = misma serie, 30/día (9 nuevas) OK');
