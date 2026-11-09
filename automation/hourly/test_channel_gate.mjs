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
console.log('channel gate PASS');
