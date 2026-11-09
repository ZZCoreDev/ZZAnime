// 9/11: daily cap per account. Counts per UTC day, lists accounts over the cap, refuses only in "enforce" mode,
// and lets everything through when counting fails.
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {Quota,quotaAllows} from './quota.mjs';
import {handle} from './channel_gate.mjs';
function fakeState(){const db=new DatabaseSync(':memory:');return {storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*(select)/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}};}
function namespace(){const obj=new Quota(fakeState());return {idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};}
const env={QUOTA:namespace(),QUOTA_DAY:'3'};
for(let i=0;i<3;i++)assert.equal(await quotaAllows(env,'user-1'),true);
assert.equal(await quotaAllows(env,'user-1'),true,'count mode never refuses');
assert.equal(await quotaAllows({...env,QUOTA_MODE:'enforce'},'user-1'),false,'enforce refuses over the cap');
assert.equal(await quotaAllows({...env,QUOTA_MODE:'enforce'},'user-2'),true);
const report=await (await env.QUOTA.get().fetch('https://quota/report?cap=3')).json();
const today=Object.values(report.days)[0];assert.equal(today.accounts,2);assert.equal(today.over[0].user,'user-1');assert.equal(today.over[0].n,5);
assert.equal(await quotaAllows({QUOTA:{idFromName:()=>1,get:()=>({fetch:async()=>{throw Error('down')}})},QUOTA_MODE:'enforce'},'u'),true,'failure lets through');
assert.equal(await quotaAllows({},'u'),true);
// Gate: series files count, channel.json and anonymous requests do not.
const hits=[];const qenv={ASSETS:{fetch:()=>new Response('file')},REQUIRE_SESSION:'false',QUOTA_MODE:'enforce',QUOTA_DAY:'1',QUOTA:{idFromName:()=>1,get:()=>({fetch:async u=>{hits.push(u);return Response.json({n:hits.length,over:hits.length>1});}})}};
assert.equal((await handle(new Request('https://x/series/a.bin'),qenv)).status,200);assert.equal(hits.length,0,'no session, nothing counted');
const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']),jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
const b64=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
const h=b64(JSON.stringify({alg:'ES256',kid:'q1'})),p=b64(JSON.stringify({iss:'https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',role:'authenticated',sub:'u9',exp:Math.floor(Date.now()/1000)+600}));
const tok=h+'.'+p+'.'+b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,new TextEncoder().encode(h+'.'+p)));
const jwks=async()=>new Response(JSON.stringify({keys:[{...jwk,alg:'ES256',kid:'q1'}]}));
const ask=path=>handle(new Request('https://x'+path,{headers:{Authorization:'Bearer '+tok}}),qenv,jwks);
assert.equal((await ask('/channel.json')).status,200);assert.equal(hits.length,0,'pointer not counted');
assert.equal((await ask('/series/a.bin')).status,200);assert.equal((await ask('/extra/series/b.bin')).status,429,'second file over cap of 1 in enforce mode');
assert.equal((await handle(new Request('https://x/series/a.bin',{headers:{Authorization:'Bearer '+tok}}),{...qenv,QUOTA_MODE:'count'},jwks)).status,200,'count mode lets it through');
console.log('quota PASS');
