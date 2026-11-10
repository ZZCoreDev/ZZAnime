// 10/11 (app 180): rules on opening links of distinct series/films; episode lists free; "soy humano" with Turnstile.
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {Quota,linkAllows,humanOk,forgetBans} from './quota.mjs';
function fakeState(){const db=new DatabaseSync(':memory:');return {storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const rows=s.all(...b);return {toArray:()=>rows};}s.run(...b);return {toArray:()=>[]};}}}};}
function namespace(){const obj=new Quota(fakeState());return {idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};}
const E=(x={})=>({QUOTA:namespace(),LINK_RULES:'enforce',LINK_SOFT:'3',LINK_BURST:'100',LINK_DAY:'5',LINK_NEW_DAY:'2',LINK_BAN:'8',...x});
// off / count: never refuses
for(const mode of ['off','count'])for(let i=0;i<20;i++)assert.equal(await linkAllows(E({LINK_RULES:mode}),{user:'a',item:'s'+i}),'ok');
// reopening the same item is free; soft threshold asks the check; human passes; cap refuses
{const e=E();const seq=[];for(let i=0;i<3;i++)seq.push(await linkAllows(e,{user:'u1',item:'s'+i}));
 for(let i=0;i<10;i++)seq.push(await linkAllows(e,{user:'u1',item:'s0'}));
 assert.deepEqual(seq,Array(13).fill('ok'),'3 distinct + reopenings');
 assert.equal(await linkAllows(e,{user:'u1',item:'s3'}),'human','4th distinct needs the check');
 assert.equal(await linkAllows(e,{user:'u1',item:'s3',human:true}),'ok');
 assert.equal(await linkAllows(e,{user:'u1',item:'s3'}),'ok','already opened: no new check');
 assert.equal(await linkAllows(e,{user:'u1',item:'s4',human:true}),'ok');
 assert.equal(await linkAllows(e,{user:'u1',item:'s5',human:true}),'limit','cap 5');
 assert.equal(await linkAllows(e,{user:'u1',item:'s1'}),'ok','opened ones still work after the cap');
 assert.equal(await linkAllows(e,{user:'u2',item:'s5'}),'ok','other accounts unaffected');}
// burst: more than LINK_BURST distinct in 10 minutes
{const e=E({LINK_SOFT:'50',LINK_BURST:'4',LINK_DAY:'150'});const r=[];for(let i=0;i<6;i++)r.push(await linkAllows(e,{user:'b',item:'x'+i}));assert.deepEqual(r,['ok','ok','ok','ok','human','human']);}
// new accounts: cap 2
{const e=E();assert.deepEqual([await linkAllows(e,{user:'n',fresh:true,item:'a'}),await linkAllows(e,{user:'n',fresh:true,item:'b'}),await linkAllows(e,{user:'n',fresh:true,item:'c',human:true})],['ok','ok','limit']);}
// ban after LINK_BAN attempts (cap refusals count, check requests do not); device banned too; owner exempt
forgetBans();{const e=E();let bans=0;const ban=async()=>{bans++;return {banned:true};},dev='0123456789abcdef0123456789abcdef';
 const r=[];for(let i=0;i<12;i++)r.push(await linkAllows(e,{user:'bad',device:dev,item:'z'+i,human:true,ban}));
 assert.deepEqual(r,['ok','ok','ok','ok','ok','limit','limit','limit','limit','limit','limit','limit']);assert.equal(bans,1);
 forgetBans();assert.equal(await linkAllows(e,{user:'fresh-account',device:dev,item:'q'}),'limit','banned device');}
forgetBans();{const e=E();for(let i=0;i<12;i++)await linkAllows(e,{user:'owner',item:'o'+i,human:true,ban:async()=>({banned:false})});
 assert.equal(await linkAllows(e,{user:'owner',item:'o99'}),'ok','exempt owner');}
// failures let through
assert.equal(await linkAllows({LINK_RULES:'enforce',QUOTA:{idFromName:()=>1,get:()=>({fetch:async()=>{throw Error('down');}})}},{user:'x',item:'y'}),'ok');
assert.equal(await linkAllows({LINK_RULES:'enforce'},{user:'x',item:'y'}),'ok');
// report shows distinct link openings
{const ns=namespace(),e={QUOTA:ns,LINK_RULES:'count'};for(let i=0;i<3;i++)await linkAllows(e,{user:'r',item:'i'+i});const rep=await (await ns.get().fetch('https://quota/report')).json();assert.deepEqual(Object.values(rep.links)[0],{accounts:1,top:3,over50:0});}
// Turnstile siteverify
{let sent=null;const f=async(u,init)=>{sent={u,body:String(init.body)};return new Response(JSON.stringify({success:true,hostname:'zzanime.uk'}));};
 assert.equal(await humanOk({TURNSTILE_SECRET:'sec'},'tok-1234567890','1.2.3.4',f),true);assert.match(sent.u,/siteverify$/);assert.match(sent.body,/secret=sec/);assert.match(sent.body,/remoteip=1.2.3.4/);
 assert.equal(await humanOk({},'tok-1234567890','',f),false,'no secret');assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'bad token!','',f),false);
 assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'tok-1234567890','',async()=>new Response('{"success":true,"hostname":"evil.example"}')),false,'other site');
 assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'tok-1234567890','',async()=>new Response('{"success":false}')),false);
 assert.equal(await humanOk({TURNSTILE_SECRET:'s'},'tok-1234567890','',async()=>{throw Error('x');}),false);}
console.log('link rules PASS');
