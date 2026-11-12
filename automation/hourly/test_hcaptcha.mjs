// 13/11/2026 (Robin): hCaptcha at the same time as the Cloudflare box, then the pictures. Real channel + Quota (SQLite in
// memory): the page marks the challenge through /humano/h (api.hcaptcha.com faked); with hCaptcha required, the box and
// the right picture are not enough without that mark.
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {handle,resetKeys,resetSeriesMaps} from './channel_gate.mjs';
import {Quota,forgetBans,quizTarget,hcaptchaPassed,HCAPTCHA_SITEKEY} from './quota.mjs';
import {publication} from './test_publicacion.mjs';
const ISS='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1';
const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']),jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
const b64=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
async function token(c){const h=b64(JSON.stringify({alg:'ES256',kid:'k1'})),p=b64(JSON.stringify(c));return h+'.'+p+'.'+b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,new TextEncoder().encode(h+'.'+p)));}
const db=new DatabaseSync(':memory:'),obj=new Quota({storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}});
let cdata='',hcaptcha={success:true,hostname:'zzanime.uk'},sent=[];
const net=async(url,init)=>{const u=String(url);
 if(u.includes('api.hcaptcha.com/siteverify')){const f=new URLSearchParams(String(init.body));sent.push(Object.fromEntries(f));return new Response(JSON.stringify(f.get('response')==='usado'?{success:false}:hcaptcha));}
 if(u.includes('siteverify'))return new Response(JSON.stringify({success:true,hostname:'zzanime.uk',action:'enlaces',cdata}));
 if(u.includes('zz_editor_access'))return new Response('{"allowed":false,"aal2":false}');return new Response(JSON.stringify({keys:[{...jwk,alg:'ES256',kid:'k1'}]}));};
const pub=publication(),QUOTA={idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};
const env={ASSETS:pub,REQUIRE_SESSION:'true',LINK_RULES:'enforce',QUOTA_MODE:'enforce',TURNSTILE_SECRET:'s',HCAPTCHA_SECRET:'h',HCAPTCHA_RULES:'required',QUOTA};
resetKeys();forgetBans();resetSeriesMaps();
const tk=await token({iss:ISS,role:'authenticated',aud:'authenticated',sub:'hcaptcha',exp:Math.floor(Date.now()/1000)+600});
const file=n=>{const f='series/'+n.repeat(64).slice(0,64)+'.bin';pub.add('',f,pub.key(n));return f;};
const get=(f,human)=>handle(new Request('https://respaldo.zzanime.uk/'+f,{headers:{Authorization:'Bearer '+tk,...(human?{'X-ZZ-Human':'tok-1234567890:q'+quizTarget(cdata)}:{})}}),env,net);
const mark=(n,t,origin='https://zzanime.uk')=>handle(new Request('https://respaldo.zzanime.uk/humano/h',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded',Origin:origin,'CF-Connecting-IP':'203.0.113.9'},body:new URLSearchParams({n,t})}),env,net);
for(const c of 'abc')assert.equal((await get(file(c))).status,200);
let r=await get(file('d'));assert.equal(r.status,428);cdata=(await r.json()).challenge;
// box + right picture but no hCaptcha: refused
assert.equal((await get(file('d'),true)).status,428,'without hCaptcha the box and the picture are not enough');
r=await get(file('d'));cdata=(await r.json()).challenge;
// hCaptcha: the page posts its token with the challenge; CORS only for zzanime.uk; sitekey and IP go to api.hcaptcha.com
r=await mark(cdata,'P1_token-hcaptcha.valido');assert.equal(r.status,200);assert.deepEqual(await r.json(),{ok:true});
assert.equal(r.headers.get('Access-Control-Allow-Origin'),'https://zzanime.uk');
assert.equal(sent.at(-1).sitekey,HCAPTCHA_SITEKEY);assert.equal(sent.at(-1).secret,'h');assert.equal(sent.at(-1).remoteip,'203.0.113.9');
assert.equal(await hcaptchaPassed(env,cdata),true);
assert.equal((await get(file('d'),true)).status,200,'box + hCaptcha + picture: opens');
// the next series needs a NEW hCaptcha (the mark is for that challenge only)
r=await get(file('e'));cdata=(await r.json()).challenge;assert.equal((await get(file('e'),true)).status,428,'old hCaptcha does not count for a new challenge');
// refused hCaptcha (reused, wrong site, other domain) marks nothing
assert.deepEqual(await (await mark(cdata,'usado')).json(),{ok:false},'reused token');
hcaptcha={success:true,hostname:'evil.example'};assert.deepEqual(await (await mark(cdata,'P1_otro-token-valido')).json(),{ok:false},'other hostname');
hcaptcha={success:true,hostname:'zzanime.uk'};
for(const [n,t] of [['xyz','P1_token-hcaptcha.valido'],[cdata,''],[cdata,'con espacios no']])assert.equal((await (await mark(n,t)).json()).ok,false,n+'/'+t);
assert.equal(await hcaptchaPassed(env,cdata),false);
// without the secret nothing is marked
assert.equal((await (await handle(new Request('https://respaldo.zzanime.uk/humano/h',{method:'POST',body:new URLSearchParams({n:cdata,t:'P1_token-hcaptcha.valido'})}),{...env,HCAPTCHA_SECRET:''},net)).json()).ok,false);
// GET (the editor asks through its binding) and preflight
assert.deepEqual(await (await handle(new Request('https://respaldo.zzanime.uk/humano/h?n='+'0'.repeat(32)),env,net)).json(),{ok:false});
assert.equal((await handle(new Request('https://respaldo.zzanime.uk/humano/h',{method:'OPTIONS'}),env,net)).status,204);
// the editor asks the mark through its ARCHIVE binding
await mark(cdata,'P1_token-para-editor');
const editorEnv={ARCHIVE:{fetch:req=>handle(req,env,net)}};assert.equal(await hcaptchaPassed(editorEnv,cdata),true,'editor sees the mark');
assert.equal(await hcaptchaPassed(editorEnv,'1'.repeat(32)),false);
console.log('hCaptcha: casilla + hCaptcha + dibujo; marca solo con hCaptcha confirmado, por reto; editor la consulta OK');
