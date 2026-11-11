// 10/11/2026 (REVISION-2 N5): with REQUIRE_SESSION "true" a report without a valid ZZAnime session is refused;
// with "false" (until 176 is the minimum version) nothing changes.
import assert from 'node:assert/strict';
import {handle} from './logic.js';
import {sessionUser,resetSessionKeys} from './session.js';
const ISS='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1';
const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']),jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
const b64=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
const h=b64(JSON.stringify({alg:'ES256',kid:'h1'})),p=b64(JSON.stringify({iss:ISS,role:'authenticated',aud:'authenticated',sub:'acct-1',exp:Math.floor(Date.now()/1000)+600}));
const tok=h+'.'+p+'.'+b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,new TextEncoder().encode(h+'.'+p)));
const fetcher=async()=>new Response(JSON.stringify({keys:[{...jwk,alg:'ES256',kid:'h1'}]}));
resetSessionKeys();
assert.equal(await sessionUser(new Request('https://x',{headers:{Authorization:'Bearer '+tok}}),fetcher),'acct-1');
assert.equal(await sessionUser(new Request('https://x'),fetcher),'');
const body=JSON.stringify({schema:1,device:'d'.repeat(20),items:[{episode:'https://jkanime.net/a/1/',name:'Mega',url:'https://mega.nz/embed/x'}]});
const r=await handle(new Request('https://ayuda.zzanime.uk/v1/dead',{method:'POST',body}),{REQUIRE_SESSION:'true',SALT:'s'},{},{fetch:fetcher});
assert.equal(r.status,401);assert.equal((await r.json()).reason,'login');
const off=await handle(new Request('https://ayuda.zzanime.uk/v1/dead',{method:'POST',body}),{REQUIRE_SESSION:'false',SALT:'s'},{},{fetch:fetcher});
assert.notEqual(off.status,401,'not required yet: old behaviour');
console.log('help session PASS');

// 11/11 quinta revisión (M-01 JWKS): Supabase rota sus llaves. Un kid nuevo recarga el juego una vez (compartida entre
// peticiones simultáneas), un kid inventado no recarga más de una vez cada 30 s y una recarga fallida conserva las llaves.
async function rotationCheck(CHECK,RESET){
 const b=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
 const mk=async kid=>{const pr=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']);return {kid,pr,jwk:{...await crypto.subtle.exportKey('jwk',pr.publicKey),alg:'ES256',kid}};};
 const sign=async(k,sub,now)=>{const h=b(JSON.stringify({alg:'ES256',kid:k.kid})),p=b(JSON.stringify({iss:'https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',role:'authenticated',aud:'authenticated',sub,exp:Math.floor(now/1000)+600}));return h+'.'+p+'.'+b(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},k.pr.privateKey,new TextEncoder().encode(h+'.'+p)));};
 const old=await mk('old'),neu=await mk('new'),bogus=await mk('bogus');let published=[old.jwk],calls=0,down=false;
 const jwks=async()=>{calls++;await new Promise(r=>setTimeout(r,5));return down?new Response('x',{status:503}):new Response(JSON.stringify({keys:published}));};
 const t0=Date.now();RESET();
 assert.equal(await CHECK(await sign(old,'a',t0),jwks,t0),'a');assert.equal(calls,1);
 published=[old.jwk,neu.jwk];const tn=await sign(neu,'b',t0);
 assert.equal(await CHECK(tn,jwks,t0+1000),'');assert.equal(calls,1,'sexta W6-01: one pause for every reload, also right after the first load');
 assert.deepEqual(await Promise.all([CHECK(tn,jwks,t0+31000),CHECK(tn,jwks,t0+31000),CHECK(tn,jwks,t0+31000)]),['b','b','b']);assert.equal(calls,2);
 const tb=await sign(bogus,'c',t0);
 assert.equal(await CHECK(tb,jwks,t0+32000),'');assert.equal(calls,2);
 assert.equal(await CHECK(tb,jwks,t0+70000),'');assert.equal(calls,3);
 assert.equal(await CHECK(tb,jwks,t0+71000),'');assert.equal(calls,3);
 down=true;await assert.rejects(()=>CHECK(tb,jwks,t0+110000),/JWKS unavailable/,'unknown kid and keys unreadable: unavailable (503), not «no session»');assert.equal(calls,4);
 assert.equal(await CHECK(tn,jwks,t0+111000),'b');assert.equal(await CHECK(await sign(old,'a',t0),jwks,t0+111000),'a');
 // Expired cache with the key set down: unavailable, at most one try every 30 s; back to normal once it answers.
 const T=t0+3700000,tt=await sign(neu,'d',T);
 await assert.rejects(()=>CHECK(tt,jwks,T),/JWKS unavailable/);await assert.rejects(()=>CHECK(tt,jwks,T+1000),/JWKS unavailable/);await assert.rejects(()=>CHECK(tt,jwks,T+2000),/JWKS unavailable/);assert.equal(calls,5);
 down=false;await assert.rejects(()=>CHECK(tt,jwks,T+10000),/JWKS unavailable/,'still in the pause');assert.equal(calls,5);
 assert.equal(await CHECK(tt,jwks,T+31000),'d');assert.equal(calls,6);
 RESET();
}
await rotationCheck((tok,f,now)=>sessionUser(new Request('https://x',{headers:{Authorization:'Bearer '+tok}}),f,now),resetSessionKeys);console.log('rotación de llaves OK');
