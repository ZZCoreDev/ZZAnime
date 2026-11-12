// 169: zzanime-respaldo keeps channel.json public; link files need a session or the cloud key when REQUIRE_SESSION is "true".
import assert from 'node:assert/strict';
import {handle,resetKeys} from './channel_gate.mjs';
const ISS='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1';
const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']),jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
const b64=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
async function token(c){const h=b64(JSON.stringify({alg:'ES256',kid:'k1'})),p=b64(JSON.stringify(c));return h+'.'+p+'.'+b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,new TextEncoder().encode(h+'.'+p)));}
const fetcher=async()=>new Response(JSON.stringify({keys:[{...jwk,alg:'ES256',kid:'k1'}]}));
const assets={fetch:()=>new Response('file')},on={ASSETS:assets,REQUIRE_SESSION:'true',CLOUD_KEY:'cloud-secret-123'};
const get=(path,headers={},env=on)=>handle(new Request('https://respaldo.zzanime.uk'+path,{headers}),env,fetcher);
resetKeys();const t=await token({iss:ISS,role:'authenticated',aud:'authenticated',sub:'u1',exp:Math.floor(Date.now()/1000)+600});
assert.equal((await get('/channel.json')).status,200);assert.equal((await get('/voe/channel.json')).status,200);
{// 12/11 M-03: series files while the daily counter is down -> 503 Retry-After 120, never served without a limit.
 const down={idFromName:()=>1,get:()=>({fetch:async()=>{throw Error('down')}})},hdr={Authorization:'Bearer '+t};
 for(const p of ['/series/x.bin','/voe/series/x.bin','/extra/series/x.bin']){const r=await get(p,hdr,{...on,QUOTA:down,QUOTA_MODE:'enforce'});assert.equal(r.status,503,p);assert.equal(r.headers.get('Retry-After'),'120');assert.equal(r.headers.get('Cache-Control'),'private, no-store');}
 assert.equal((await get('/series/x.bin',hdr,{...on,QUOTA:down,QUOTA_MODE:'enforce',LINK_RULES:'enforce'})).status,503,'link rules enforced: also closed');
 assert.equal((await get('/series/x.bin',hdr,{...on,QUOTA:down,QUOTA_MODE:'count'})).status,200,'counting only: unchanged');
 assert.equal((await get('/channel.json',hdr,{...on,QUOTA:down,QUOTA_MODE:'enforce'})).status,200,'channel pointer does not need the counter');}
assert.equal((await get('/indexes/'+'a'.repeat(64)+'.bin')).status,401);
assert.equal((await get('/series/'+'a'.repeat(64)+'.bin',{Authorization:'Bearer '+t})).status,200);
assert.equal((await get('/series/x.bin',{'X-ZZ-Cloud':'cloud-secret-123'})).status,200);
assert.equal((await get('/series/x.bin',{'X-ZZ-Cloud':'wrong'})).status,401);
assert.equal((await get('/series/x.bin',{},{...on,REQUIRE_SESSION:'false'})).status,200);
assert.equal((await get('/series/x.bin',{'X-ZZ-Cloud':''},{...on,CLOUD_KEY:''})).status,401);
assert.equal((await get('/series/x.bin',{Authorization:'Bearer '+t},{...on,CHANNEL_LIMIT:{limit:async()=>({success:false})}})).status,429);
// 9/11: anonymous sessions are not accounts; /owner/ only for the editor owner with authenticator.
const anon=await token({iss:ISS,role:'authenticated',aud:'authenticated',sub:'u2',is_anonymous:true,exp:Math.floor(Date.now()/1000)+600});
assert.equal((await get('/series/x.bin',{Authorization:'Bearer '+anon})).status,401);
const ownerToken='o'.repeat(40),plainToken='p'.repeat(40);
const ownerFetch=async(url,init)=>String(url).endsWith('/rpc/zz_editor_access')?(init.headers.Authorization==='Bearer '+ownerToken?new Response('{"allowed":true,"aal2":true}'):init.headers.Authorization==='Bearer '+plainToken?new Response('{"allowed":true,"aal2":false}'):new Response('{}',{status:400})):fetcher(url,init);
const own=(path,auth)=>handle(new Request('https://respaldo.zzanime.uk'+path,{headers:auth?{Authorization:'Bearer '+auth}:{}}),on,ownerFetch);
assert.equal((await own('/owner/link-health.json',ownerToken)).status,200);assert.equal((await own('/owner/link-health-3.json',ownerToken)).status,200);assert.equal((await own('/owner/help-status.json',ownerToken)).status,200);
assert.equal((await own('/owner/link-health.json',plainToken)).status,403);assert.equal((await own('/owner/link-health.json')).status,403);assert.equal((await own('/owner/link-health.json',t)).status,403);
assert.equal((await own('/owner/other.json',ownerToken)).status,404);assert.equal((await own('/owner/cloud-runs.json',ownerToken)).status,200);assert.equal((await own('/owner/cloud-runs.json')).status,403);
assert.equal((await handle(new Request('https://respaldo.zzanime.uk/owner/link-health.json',{headers:{'X-ZZ-Cloud':'cloud-secret-123'}}),on,ownerFetch)).status,403);
// 9/11: the daily-cap report answers the owner or the cloud key (health_watch.py); a wrong key or none is refused.
{const qon={...on,QUOTA:{idFromName:()=>'g',get:()=>({fetch:async()=>new Response('{"schema":1,"bans":[]}')})}};
 const q=headers=>handle(new Request('https://respaldo.zzanime.uk/owner/quota.json',{headers}),qon,ownerFetch);
 const ok=await q({'X-ZZ-Cloud':'cloud-secret-123'});assert.equal(ok.status,200);assert.equal((await ok.json()).schema,1);assert.equal(ok.headers.get('Cache-Control'),'no-store');
 assert.equal((await q({Authorization:'Bearer '+ownerToken})).status,200);
 assert.equal((await q({'X-ZZ-Cloud':'wrong'})).status,403);assert.equal((await q({})).status,403);assert.equal((await q({Authorization:'Bearer '+plainToken})).status,403);
 assert.equal((await handle(new Request('https://x/owner/quota.json',{headers:{'X-ZZ-Cloud':''}}),{...qon,CLOUD_KEY:''},ownerFetch)).status,403,'empty key never matches');}
console.log('channel gate PASS');
// 10/11: old workers.dev host = pointer + cloud check only.
{const old=(p,h={})=>handle(new Request('https://zzanime-respaldo.zzcoredev.workers.dev'+p,{headers:h}),{...on,REQUIRE_SESSION:'false'},fetcher);
 assert.equal((await old('/channel.json')).status,200);assert.equal((await old('/voe/channel.json')).status,200);
 assert.equal((await old('/series/x.bin')).status,200,'old address open again (179 fallback)');assert.equal((await old('/series/x.bin',{'X-ZZ-Cloud':'cloud-secret-123'})).status,200);
 assert.equal((await handle(new Request('https://respaldo.zzanime.uk/series/x.bin'),{...on,REQUIRE_SESSION:'false'},fetcher)).status,200,'new domain unchanged');
 console.log('old host PASS');}

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
{const {sessionUser:SU}=await import('./channel_gate.mjs');await rotationCheck((tok,f,now)=>SU(new Request('https://x',{headers:{Authorization:'Bearer '+tok}}),f,now),resetKeys);console.log('rotación de llaves OK');}

// 11/11 quinta revisión M-05: the 428 carries a challenge bound to the account and series; only a Siteverify answer with
// that same cData opens it, once (afterwards a 30-minute window).
{const {DatabaseSync}=await import('node:sqlite');const {Quota,quizTarget}=await import('./quota.mjs');const {handle:H,resetKeys:R}=await import('./channel_gate.mjs');
 const db=new DatabaseSync(':memory:'),state={storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}};
 const obj=new Quota(state),QUOTA={idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};
 let cdata='',verifies=0;const net=async(url,init)=>{if(String(url).includes('siteverify')){verifies++;return new Response(JSON.stringify({success:true,hostname:'zzanime.uk',action:'enlaces',cdata}));}return fetcher(url,init);};
 const pub=(await import('./test_publicacion.mjs')).publication(),reg=p=>{const m=/^\/((?:voe|extra)\/)?(series\/([^/]+)\.bin)$/.exec(p);if(m)pub.add(m[1]||'',m[2],pub.key(m[3]));return p;};
 const env={ASSETS:pub,REQUIRE_SESSION:'true',LINK_RULES:'enforce',LINK_SOFT:'1',LINK_BURST:'100',LINK_DAY:'10',LINK_BAN:'50',TURNSTILE_SECRET:'s',QUOTA};
 R();const tk=await token({iss:ISS,role:'authenticated',aud:'authenticated',sub:'hum-1',exp:Math.floor(Date.now()/1000)+600});
 const open=(path,human)=>H(new Request('https://respaldo.zzanime.uk'+reg(path),{headers:{Authorization:'Bearer '+tk,...(human?{'X-ZZ-Human':'tok-1234567890:q'+(/^[a-f0-9]{32}$/.test(cdata)?quizTarget(cdata):0)}:{})}}),env,net);
 assert.equal((await open('/series/a.bin')).status,200);
 const first=await open('/series/b.bin');assert.equal(first.status,428);const {challenge}=await first.json();assert.match(challenge,/^[a-f0-9]{32}$/);
 cdata='';assert.equal((await open('/series/b.bin',true)).status,428,'token without challenge (page of 188)');
 cdata='0'.repeat(32);assert.equal((await open('/series/b.bin',true)).status,428,'invented challenge');
 const latest=await (await open('/series/b.bin')).json();cdata=latest.challenge;
 assert.equal((await open('/series/b.bin',true)).status,200,'own challenge opens it');
 assert.equal((await open('/series/c.bin')).status,200,'30-minute window');
 console.log('soy humano ligado a cuenta y serie OK');}

// 12/11 sexta revisión: W6-02 the editor owner with aal2 is not asked (editor relay); W6-01 key set down → 503, not 401.
{const {DatabaseSync}=await import('node:sqlite');const {Quota,quizTarget}=await import('./quota.mjs');const {handle:H,resetKeys:R}=await import('./channel_gate.mjs');
 const db=new DatabaseSync(':memory:'),state={storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}};
 const obj=new Quota(state),QUOTA={idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};let isOwner=false,ownerCalls=0;
 const net=async(url,init)=>{if(String(url).endsWith('/rpc/zz_editor_access')){ownerCalls++;return new Response(JSON.stringify({allowed:isOwner,aal2:isOwner}));}return fetcher(url,init);};
 const pub=(await import('./test_publicacion.mjs')).publication(),reg=p=>{const m=/^\/((?:voe|extra)\/)?(series\/([^/]+)\.bin)$/.exec(p);if(m)pub.add(m[1]||'',m[2],pub.key(m[3]));return p;};
 const env={ASSETS:pub,REQUIRE_SESSION:'true',LINK_RULES:'enforce',LINK_SOFT:'1',LINK_BURST:'100',LINK_DAY:'10',LINK_BAN:'50',TURNSTILE_SECRET:'s',QUOTA};
 R();const tk=await token({iss:ISS,role:'authenticated',aud:'authenticated',sub:'owner-1',exp:Math.floor(Date.now()/1000)+600});
 const open=p=>H(new Request('https://respaldo.zzanime.uk'+reg(p),{headers:{Authorization:'Bearer '+tk}}),env,net);
 assert.equal((await open('/series/a.bin')).status,200);assert.equal(ownerCalls,0,'Supabase only asked when the check would be asked');
 assert.equal((await open('/series/b.bin')).status,428,'not owner: asked');assert.equal(ownerCalls,1);
 isOwner=true;assert.equal((await open('/series/b.bin')).status,200,'editor owner with aal2: not asked');
 R();const down=async()=>new Response('x',{status:503});const r=await H(new Request('https://respaldo.zzanime.uk/series/a.bin',{headers:{Authorization:'Bearer '+tk}}),env,down);
 assert.equal(r.status,503);assert.equal(r.headers.get('Retry-After'),'30');R();
 console.log('dueño sin casilla y llaves caídas 503 OK');}
{// 12/11 R8-01: anonymous pointer reads spend the counter at most once every 50 (per instance), never once per read.
 let calls=0;const counting={idFromName:()=>1,get:()=>({fetch:async()=>{calls++;return new Response('{}');}})};
 for(let i=0;i<24;i++)assert.equal((await handle(new Request('https://respaldo.zzanime.uk/channel.json'),{...on,QUOTA:counting},fetcher)).status,200);
 assert.ok(calls<=1,'pointer telemetry sampled: '+calls);
 calls=0;for(let i=0;i<3;i++)assert.equal((await handle(new Request('https://respaldo.zzanime.uk/series/'+'c'.repeat(64)+'.bin'),{...on,QUOTA:counting,QUOTA_MODE:'enforce'},fetcher)).status,401);
 assert.equal(calls,0,'no session: 401 before the counter');
 console.log('R8-01 puntero y anónimos sin gastar el contador OK');}
