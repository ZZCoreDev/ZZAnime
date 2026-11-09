// 169: zzanime-respaldo keeps channel.json public; link files need a session or the cloud key when REQUIRE_SESSION is "true".
import assert from 'node:assert/strict';
import {handle,resetKeys} from './channel_gate.mjs';
const ISS='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1';
const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']),jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
const b64=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
async function token(c){const h=b64(JSON.stringify({alg:'ES256',kid:'k1'})),p=b64(JSON.stringify(c));return h+'.'+p+'.'+b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,new TextEncoder().encode(h+'.'+p)));}
const fetcher=async()=>new Response(JSON.stringify({keys:[{...jwk,alg:'ES256',kid:'k1'}]}));
const assets={fetch:()=>new Response('file')},on={ASSETS:assets,REQUIRE_SESSION:'true',CLOUD_KEY:'cloud-secret-123'};
const get=(path,headers={},env=on)=>handle(new Request('https://zzanime-respaldo.zzcoredev.workers.dev'+path,{headers}),env,fetcher);
resetKeys();const t=await token({iss:ISS,role:'authenticated',sub:'u1',exp:Math.floor(Date.now()/1000)+600});
assert.equal((await get('/channel.json')).status,200);assert.equal((await get('/voe/channel.json')).status,200);
assert.equal((await get('/indexes/'+'a'.repeat(64)+'.bin')).status,401);
assert.equal((await get('/series/'+'a'.repeat(64)+'.bin',{Authorization:'Bearer '+t})).status,200);
assert.equal((await get('/series/x.bin',{'X-ZZ-Cloud':'cloud-secret-123'})).status,200);
assert.equal((await get('/series/x.bin',{'X-ZZ-Cloud':'wrong'})).status,401);
assert.equal((await get('/series/x.bin',{},{...on,REQUIRE_SESSION:'false'})).status,200);
assert.equal((await get('/series/x.bin',{'X-ZZ-Cloud':''},{...on,CLOUD_KEY:''})).status,401);
assert.equal((await get('/series/x.bin',{Authorization:'Bearer '+t},{...on,CHANNEL_LIMIT:{limit:async()=>({success:false})}})).status,429);
// 9/11: anonymous sessions are not accounts; /owner/ only for the editor owner with authenticator.
const anon=await token({iss:ISS,role:'authenticated',sub:'u2',is_anonymous:true,exp:Math.floor(Date.now()/1000)+600});
assert.equal((await get('/series/x.bin',{Authorization:'Bearer '+anon})).status,401);
const ownerToken='o'.repeat(40),plainToken='p'.repeat(40);
const ownerFetch=async(url,init)=>String(url).endsWith('/rpc/zz_editor_access')?(init.headers.Authorization==='Bearer '+ownerToken?new Response('{"allowed":true,"aal2":true}'):init.headers.Authorization==='Bearer '+plainToken?new Response('{"allowed":true,"aal2":false}'):new Response('{}',{status:400})):fetcher(url,init);
const own=(path,auth)=>handle(new Request('https://zzanime-respaldo.zzcoredev.workers.dev'+path,{headers:auth?{Authorization:'Bearer '+auth}:{}}),on,ownerFetch);
assert.equal((await own('/owner/link-health.json',ownerToken)).status,200);assert.equal((await own('/owner/link-health-3.json',ownerToken)).status,200);assert.equal((await own('/owner/help-status.json',ownerToken)).status,200);
assert.equal((await own('/owner/link-health.json',plainToken)).status,403);assert.equal((await own('/owner/link-health.json')).status,403);assert.equal((await own('/owner/link-health.json',t)).status,403);
assert.equal((await own('/owner/other.json',ownerToken)).status,404);assert.equal((await own('/owner/cloud-runs.json',ownerToken)).status,200);assert.equal((await own('/owner/cloud-runs.json')).status,403);
assert.equal((await handle(new Request('https://zzanime-respaldo.zzcoredev.workers.dev/owner/link-health.json',{headers:{'X-ZZ-Cloud':'cloud-secret-123'}}),on,ownerFetch)).status,403);
// 9/11: the daily-cap report answers the owner or the cloud key (health_watch.py); a wrong key or none is refused.
{const qon={...on,QUOTA:{idFromName:()=>'g',get:()=>({fetch:async()=>new Response('{"schema":1,"bans":[]}')})}};
 const q=headers=>handle(new Request('https://zzanime-respaldo.zzcoredev.workers.dev/owner/quota.json',{headers}),qon,ownerFetch);
 const ok=await q({'X-ZZ-Cloud':'cloud-secret-123'});assert.equal(ok.status,200);assert.equal((await ok.json()).schema,1);assert.equal(ok.headers.get('Cache-Control'),'no-store');
 assert.equal((await q({Authorization:'Bearer '+ownerToken})).status,200);
 assert.equal((await q({'X-ZZ-Cloud':'wrong'})).status,403);assert.equal((await q({})).status,403);assert.equal((await q({Authorization:'Bearer '+plainToken})).status,403);
 assert.equal((await handle(new Request('https://x/owner/quota.json',{headers:{'X-ZZ-Cloud':''}}),{...qon,CLOUD_KEY:''},ownerFetch)).status,403,'empty key never matches');}
console.log('channel gate PASS');
