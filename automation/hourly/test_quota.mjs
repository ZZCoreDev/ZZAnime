// 9/11: daily cap per account and per IP; abusive accounts banned through Supabase (028); owner/exempt never banned;
// counting failures let everything through.
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {Quota,quotaAllows,forgetBans} from './quota.mjs';
import {handle} from './channel_gate.mjs';
function fakeState(){const db=new DatabaseSync(':memory:');return {storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}};}
function namespace(){const obj=new Quota(fakeState());return {idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};}
// count mode: never refuses
let env={QUOTA:namespace(),QUOTA_DAY:'3'};
for(let i=0;i<8;i++)assert.equal(await quotaAllows(env,{user:'user-1'}),true);
// enforce: refused over the cap, banned past QUOTA_BAN (default 2x cap)
env={QUOTA:namespace(),QUOTA_DAY:'3',QUOTA_MODE:'enforce'};let bans=0;const ban=async()=>{bans++;return {banned:true};};
const seq=[];for(let i=0;i<8;i++)seq.push(await quotaAllows(env,{user:'user-2',ban}));
assert.deepEqual(seq,[true,true,true,false,false,false,false,false]);assert.equal(bans,1,'banned once (7th request)');
assert.equal(await quotaAllows(env,{user:'user-2',ban}),false,'stays refused after the ban');
const rep=await (await env.QUOTA.get().fetch('https://quota/report?cap=3')).json();assert.equal(rep.bans[0].user,'user-2');
// owner/exempt: Supabase answers banned:false -> let through for good
let asked=0;const exempt=async()=>{asked++;return {banned:false};};
for(let i=0;i<10;i++)assert.equal(await quotaAllows(env,{user:'owner-1',ban:exempt}),i<3||i>=6,'refused only between cap and ban threshold, then exempt');
assert.equal(asked,1);
// Supabase unreachable (028 missing): local 6 h refusal instead of a ban
const local=namespace();env={QUOTA:local,QUOTA_DAY:'1',QUOTA_MODE:'enforce'};
for(let i=0;i<3;i++)await quotaAllows(env,{user:'user-3',ban:async()=>null});
assert.equal(await quotaAllows(env,{user:'user-3',ban:async()=>null}),false);
// anonymous IP: own cap, never banned
env={QUOTA:namespace(),QUOTA_IP_DAY:'2',QUOTA_MODE:'enforce'};
assert.deepEqual([await quotaAllows(env,{ip:'203.0.113.9'}),await quotaAllows(env,{ip:'203.0.113.9'}),await quotaAllows(env,{ip:'203.0.113.9'})],[true,true,false]);
assert.equal(await quotaAllows(env,{ip:'203.0.113.10'}),true);
// 12/11 M-03: a failing counter closes while the limit is enforced (QuotaUnavailable -> 503); counting-only mode and
// missing pieces still let through.
const down={idFromName:()=>1,get:()=>({fetch:async()=>{throw Error('down')}})},bad={idFromName:()=>1,get:()=>({fetch:async()=>new Response('not json')})};
await assert.rejects(()=>quotaAllows({QUOTA:down,QUOTA_MODE:'enforce'},{user:'u'}),{name:'Error',message:'Quota counter unavailable'});
await assert.rejects(()=>quotaAllows({QUOTA:bad,QUOTA_MODE:'enforce'},{user:'u'}),/Quota counter unavailable/);
assert.equal(await quotaAllows({QUOTA:down,QUOTA_MODE:'count'},{user:'u'}),true);
assert.equal(await quotaAllows({},{user:'u'}),true);assert.equal(await quotaAllows({QUOTA:namespace(),QUOTA_MODE:'enforce'},{}),true);
// Gate: series files count (by account or by IP), pointers do not; the ban asks Supabase with the caller's own session.
const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']),jwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
const b64=x=>Buffer.from(typeof x==='string'?x:new Uint8Array(x)).toString('base64url');
const h=b64(JSON.stringify({alg:'ES256',kid:'q1'})),p=b64(JSON.stringify({iss:'https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',role:'authenticated',aud:'authenticated',sub:'u9',exp:Math.floor(Date.now()/1000)+600}));
const tok=h+'.'+p+'.'+b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,new TextEncoder().encode(h+'.'+p)));
let banCalls=[];const net=async(url,init)=>{if(String(url).endsWith('/rpc/zz_quota_ban')){banCalls.push(init.headers.Authorization);return new Response('{"banned":true}');}return new Response(JSON.stringify({keys:[{...jwk,alg:'ES256',kid:'q1'}]}));};
const qenv={ASSETS:{fetch:()=>new Response('file')},REQUIRE_SESSION:'false',QUOTA_MODE:'enforce',QUOTA_DAY:'1',QUOTA_BAN:'2',QUOTA_IP_DAY:'1',QUOTA:namespace()};
const ask=(path,auth,ip)=>handle(new Request('https://x'+path,{headers:{...(auth?{Authorization:'Bearer '+auth}:{}),...(ip?{'CF-Connecting-IP':ip}:{})}}),qenv,net);
assert.equal((await ask('/channel.json',tok)).status,200);
assert.deepEqual([(await ask('/series/a.bin',tok)).status,(await ask('/voe/series/b.bin',tok)).status,(await ask('/extra/series/c.bin',tok)).status],[200,429,429]);
assert.deepEqual(banCalls,['Bearer '+tok],'banned with its own session');
assert.deepEqual([(await ask('/series/a.bin',null,'198.51.100.7')).status,(await ask('/series/a.bin',null,'198.51.100.7')).status],[200,429]);
assert.equal((await handle(new Request('https://x/series/a.bin',{headers:{'X-ZZ-Cloud':'k'}}),{...qenv,CLOUD_KEY:'k'},net)).status,200,'cloud check never counted');
// 170: the device of a banned account is banned too (a new account on the same phone gets nothing); other devices unaffected.
{const e={QUOTA:namespace(),QUOTA_DAY:'1',QUOTA_BAN:'2',QUOTA_MODE:'enforce'},dev='ab'.repeat(16),other='cd'.repeat(16),b=async()=>({banned:true});
 for(let i=0;i<3;i++)await quotaAllows(e,{user:'bad-1',device:dev,ban:b});
 assert.equal(await quotaAllows(e,{user:'new-account',device:dev,ban:b}),false,'same device, new account: refused');
 assert.equal(await quotaAllows(e,{user:'new-account',device:other,ban:b}),true,'other device fine');
 assert.equal(await quotaAllows(e,{ip:'192.0.2.5',device:dev}),false,'banned device without session refused too');
 assert.equal(await quotaAllows(e,{user:'x',device:'NOT-A-HASH'}),true,'malformed device ignored');
 const dr=await (await e.QUOTA.get().fetch('https://quota/report')).json();assert.equal(dr.bannedDevices,1);
 assert.equal(dr.deviceBans.length,1);assert.match(dr.deviceBans[0].at,/^\d{4}-\d\d-\d\dT/);assert.ok(!JSON.stringify(dr.deviceBans).includes(dev),'device hash not in the report');
 forgetBans();const ex={QUOTA:namespace(),QUOTA_DAY:'1',QUOTA_BAN:'2',QUOTA_MODE:'enforce'};for(let i=0;i<3;i++)await quotaAllows(ex,{user:'owner',device:dev,ban:async()=>({banned:false})});
 assert.equal(await quotaAllows(ex,{user:'someone',device:dev}),true,'exempt owner: device not banned');}
// 10/11: new accounts (zz_new) get a smaller daily cap; banned accounts are remembered without asking the counter again.
forgetBans();{let hits=0;const ns=namespace(),e={QUOTA:{idFromName:()=>1,get:()=>({fetch:u=>{hits++;return ns.get().fetch(u);}})},QUOTA_DAY:'5',QUOTA_NEW_DAY:'2',QUOTA_BAN:'4',QUOTA_MODE:'enforce'};
 assert.deepEqual([await quotaAllows(e,{user:'n1',fresh:true}),await quotaAllows(e,{user:'n1',fresh:true}),await quotaAllows(e,{user:'n1',fresh:true})],[true,true,false],'new account: cap 2');
 assert.equal(await quotaAllows(e,{user:'old1'}),true);
 for(let i=0;i<3;i++)await quotaAllows(e,{user:'n1',fresh:true,ban:async()=>({banned:true})});
 const before=hits;for(let i=0;i<50;i++)assert.equal(await quotaAllows(e,{user:'n1',fresh:true,ban:async()=>({banned:true})}),false);
 assert.equal(hits,before,'banned account: no more counter calls');}
{const ns=namespace(),e={QUOTA:ns};const {quotaTally}=await import('./quota.mjs');await quotaTally(e,'old');await quotaTally(e,'new');await quotaTally(e,'new');const r=await (await ns.get().fetch('https://quota/report')).json();const d=Object.values(r.days)[0];assert.deepEqual(d.hosts,{old:1,new:2});assert.equal(d.accounts,0,'host tallies are not accounts');}
console.log('quota PASS');
