// 10/11 (app 180): rules on opening links of distinct series/films; episode lists free; "soy humano" with Turnstile.
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {Quota,linkAllows,humanOk,forgetBans,quizTarget} from './quota.mjs';
function fakeState(){const db=new DatabaseSync(':memory:');return {storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}};}
function namespace(){const obj=new Quota(fakeState());return {idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};}
// 11/11 quinta revisión: passing the check = opening with the challenge the 428 gave (as Siteverify returns it in cData).
async function opened(e,args){const out={};const r=await linkAllows(e,{...args,out});if(r!=='human')return r;return linkAllows(e,{...args,human:out.challenge});}
const E=(x={})=>({QUOTA:namespace(),LINK_RULES:'enforce',LINK_SOFT:'3',LINK_BURST:'100',LINK_DAY:'5',LINK_NEW_DAY:'2',LINK_BAN:'8',...x});
// off / count: never refuses
for(const mode of ['off','count'])for(let i=0;i<20;i++)assert.equal(await linkAllows(E({LINK_RULES:mode}),{user:'a',item:'s'+i}),'ok');
// reopening the same item is free; soft threshold asks the check; human passes; cap refuses
{const e=E();const seq=[];for(let i=0;i<3;i++)seq.push(await linkAllows(e,{user:'u1',item:'s'+i}));
 for(let i=0;i<10;i++)seq.push(await linkAllows(e,{user:'u1',item:'s0'}));
 assert.deepEqual(seq,Array(13).fill('ok'),'3 distinct + reopenings');
 const out={};assert.equal(await linkAllows(e,{user:'u1',item:'s3',out}),'human','4th distinct needs the check');assert.match(out.challenge,/^[a-f0-9]{32}$/);
 assert.equal(await linkAllows(e,{user:'u1',item:'s3',human:'f'.repeat(32)}),'human','an invented challenge does nothing');
 const other={};await linkAllows(e,{user:'u2',item:'t0'});await linkAllows(e,{user:'u2',item:'t1'});await linkAllows(e,{user:'u2',item:'t2'});assert.equal(await linkAllows(e,{user:'u2',item:'t3',out:other}),'human');
 assert.equal(await linkAllows(e,{user:'u1',item:'s3',human:other.challenge}),'human','challenge of another account does nothing');
 const again={};assert.equal(await linkAllows(e,{user:'u1',item:'s4',human:out.challenge,out:again}),'human','challenge of another series does nothing');
 assert.equal(await linkAllows(e,{user:'u1',item:'s3',human:out.challenge}),'ok','its own challenge passes');
 assert.equal(await linkAllows(e,{user:'u2',item:'t3',human:other.challenge}),'ok');
 assert.equal(await linkAllows(e,{user:'u2',item:'t4',human:other.challenge}),'human','12/11 más estricta: a check opens only its own series');
 assert.equal(await linkAllows(e,{user:'u1',item:'s3'}),'ok','already opened: no new check');
 const s4={};assert.equal(await linkAllows(e,{user:'u1',item:'s4',out:s4}),'human','12/11 más estricta: the next new series asks again');
 assert.equal(await linkAllows(e,{user:'u1',item:'s4',human:s4.challenge}),'ok','its own check opens it');
 assert.equal(await linkAllows(e,{user:'u1',item:'s5'}),'limit','cap 5');
 assert.equal(await linkAllows(e,{user:'u1',item:'s1'}),'ok','opened ones still work after the cap');
 assert.equal(await linkAllows(e,{user:'u3',item:'s5'}),'ok','other accounts unaffected');}
// burst: more than LINK_BURST distinct in 10 minutes
{const e=E({LINK_SOFT:'50',LINK_BURST:'4',LINK_DAY:'150'});const r=[];for(let i=0;i<6;i++)r.push(await linkAllows(e,{user:'b',item:'x'+i}));assert.deepEqual(r,['ok','ok','ok','ok','human','human']);}
// new accounts: cap 2
{const e=E();assert.deepEqual([await linkAllows(e,{user:'n',fresh:true,item:'a'}),await linkAllows(e,{user:'n',fresh:true,item:'b'}),await opened(e,{user:'n',fresh:true,item:'c'})],['ok','ok','limit']);}
// ban after LINK_BAN attempts (cap refusals count, check requests do not); device banned too; owner exempt
forgetBans();{const e=E();let bans=0;const ban=async()=>{bans++;return {banned:true};},dev='0123456789abcdef0123456789abcdef';
 const r=[];for(let i=0;i<12;i++)r.push(await opened(e,{user:'bad',device:dev,item:'z'+i,ban}));
 assert.deepEqual(r,['ok','ok','ok','ok','ok','limit','limit','limit','limit','limit','limit','limit']);assert.equal(bans,1);
 forgetBans();assert.equal(await linkAllows(e,{user:'fresh-account',device:dev,item:'q'}),'limit','banned device');}
forgetBans();{const e=E();for(let i=0;i<12;i++)await opened(e,{user:'owner',item:'o'+i,ban:async()=>({banned:false})});
 assert.equal(await linkAllows(e,{user:'owner',item:'o99'}),'ok','exempt owner');}
// failures let through
// 12/11 M-03: enforced and the counter fails -> closed (QuotaUnavailable); only counting -> unchanged.
await assert.rejects(()=>linkAllows({LINK_RULES:'enforce',QUOTA:{idFromName:()=>1,get:()=>({fetch:async()=>{throw Error('down');}})}},{user:'x',item:'y'}),/Quota counter unavailable/);
assert.equal(await linkAllows({LINK_RULES:'count',QUOTA:{idFromName:()=>1,get:()=>({fetch:async()=>{throw Error('down');}})}},{user:'x',item:'y'}),'ok');
// 12/11 R8-02: enforced = no binding throws, no account or bad item is refused, non-counter answers close.
await assert.rejects(()=>linkAllows({LINK_RULES:'enforce'},{user:'x',item:'y'}),/Quota counter unavailable/);
assert.equal(await linkAllows({LINK_RULES:'enforce',QUOTA:namespace()},{item:'y'}),'limit');
assert.equal(await linkAllows({LINK_RULES:'enforce',QUOTA:namespace()},{user:'x',item:'bad item!'}),'limit');
assert.equal(await linkAllows({LINK_RULES:'count'},{user:'x',item:'y'}),'ok');
const answer=(status,body)=>({idFromName:()=>1,get:()=>({fetch:async()=>new Response(body,{status})})});
for(const [st,b] of [[503,'{"ok":true}'],[200,'{}'],[200,'[]'],[200,'{"ok":"yes"}']])
 await assert.rejects(()=>linkAllows({LINK_RULES:'enforce',QUOTA:answer(st,b)},{user:'x'+st+b.length,item:'y'}),/Quota counter unavailable/,st+' '+b);
assert.equal(await linkAllows({LINK_RULES:'enforce',QUOTA:answer(200,'{"over":true,"n":5,"distinct":5}')},{user:'z',item:'y'}),'limit');
// report shows distinct link openings
{const ns=namespace(),e={QUOTA:ns,LINK_RULES:'count'};for(let i=0;i<3;i++)await linkAllows(e,{user:'r',item:'i'+i});const rep=await (await ns.get().fetch('https://quota/report')).json();assert.deepEqual(Object.values(rep.links)[0],{accounts:1,top:3,over50:0});}
// Turnstile siteverify
{const C='0123456789abcdef0123456789abcdef';let sent=null;const f=async(u,init)=>{sent={u,body:String(init.body)};return new Response(JSON.stringify({success:true,hostname:'zzanime.uk',action:'enlaces',cdata:C}));};
 assert.equal(await humanOk({TURNSTILE_SECRET:'sec'},'tok-1234567890:q'+quizTarget(C),'1.2.3.4',f),C,'answers the challenge');assert.equal(await humanOk({TURNSTILE_SECRET:'sec'},'tok-1234567890','1.2.3.4',f),'','12/11: without the picture answer it does not count');assert.equal(await humanOk({TURNSTILE_SECRET:'sec'},'tok-1234567890:q'+((quizTarget(C)+1)%6),'1.2.3.4',f),'','wrong picture');assert.match(sent.u,/siteverify$/);assert.match(sent.body,/secret=sec/);assert.match(sent.body,/remoteip=1.2.3.4/);
 assert.equal(await humanOk({},'tok-1234567890','',f),'','no secret');assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'bad token!','',f),'');
 assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'tok-1234567890','',async()=>new Response('{"success":true,"hostname":"evil.example","action":"enlaces","cdata":"'+C+'"}')),'','other site');
 assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'tok-1234567890','',async()=>new Response('{"success":false}')),'');
 assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'tok-1234567890','',async()=>new Response('{"success":true,"hostname":"zzanime.uk","action":"enlaces"}')),'','no challenge (page of app 188)');
 assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'tok-1234567890','',async()=>new Response('{"success":true,"hostname":"zzanime.uk","action":"otra","cdata":"'+C+'"}')),'','other action');
 assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'tok-1234567890','',async()=>{throw Error('x');}),'');}
console.log('link rules PASS');
