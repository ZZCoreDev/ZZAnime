// 13/11/2026 (Robin, grupo 2): owner controls from the editor: only the owner with authenticator, changes need the code of
// the last 10 minutes, account and network bans apply at once, limits and the hCaptcha switch change without deploying.
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {handle,resetKeys,adminPath} from './channel_gate.mjs';
import {Quota,linkAllows,forgetBans,humanOk,quizTarget,resetOwnerConf} from './quota.mjs';
const b64=x=>Buffer.from(JSON.stringify(x)).toString('base64url');
const tok=(amrAgo)=>b64({alg:'ES256'})+'.'+b64({sub:'owner',amr:amrAgo==null?[{method:'password',timestamp:Math.floor(Date.now()/1000)}]:[{method:'totp',timestamp:Math.floor(Date.now()/1000)-amrAgo}]})+'.firma';
const db=new DatabaseSync(':memory:'),obj=new Quota({storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const r=s.all(...b);return {toArray:()=>r};}s.run(...b);return {toArray:()=>[]};}}}});
const QUOTA={idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};
let isOwner=true,cdata='';
const net=async u=>{const s=String(u);if(s.includes('zz_editor_access'))return new Response(JSON.stringify(isOwner?{allowed:true,aal2:true}:{allowed:false}));
 if(s.includes('siteverify'))return new Response(JSON.stringify({success:true,hostname:'zzanime.uk',action:'enlaces',cdata}));return new Response('{}');};
const env={QUOTA,LINK_RULES:'enforce',LINK_SOFT:'100',LINK_BURST:'100',LINK_DAY:'50',LINK_BAN:'1000',TURNSTILE_SECRET:'s',HCAPTCHA_RULES:'required',ASSETS:{fetch:()=>new Response('x')}};
const admin=(t,body)=>handle(new Request('https://respaldo.zzanime.uk/owner/admin',{method:body?'POST':'GET',headers:{Authorization:'Bearer '+t,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})}),env,net);
resetKeys();forgetBans();resetOwnerConf();
// whitelist
assert.equal(adminPath({action:'ban-user',user:'x'}),null);assert.equal(adminPath({action:'set',name:'evil',value:1}),null);assert.equal(adminPath({action:'drop'}),null);
assert.equal(adminPath({action:'ban-net',ip:'2001:db8:1:2:aaaa::9',hours:9999}),'/admin/ban?k=n:'+encodeURIComponent('2001:db8:1:2::')+'&hours=720');
// only the owner; reading needs no fresh code, changing does
isOwner=false;assert.equal((await admin(tok(60))).status,403);isOwner=true;
assert.equal((await admin(tok(null))).status,200,'owner reads');
assert.equal((await admin(tok(11*60),{action:'set',name:'cap',value:5})).status,401,'old code: reauth');
assert.equal((await admin(tok(null),{action:'set',name:'cap',value:5})).status,401,'no code');
assert.equal((await admin(tok(60),{action:'set',name:'cap',value:99999})).status,400,'out of range');
// limits from the editor
let r=await admin(tok(60),{action:'set',name:'cap',value:2});assert.equal(r.status,200);assert.equal((await r.json()).apply,'/admin/set?name=cap&value=2');
assert.equal(await linkAllows(env,{user:'a',item:'s1'}),'ok');assert.equal(await linkAllows(env,{user:'a',item:'s2'}),'ok');assert.equal(await linkAllows(env,{user:'a',item:'s3'}),'limit','owner cap 2');
await admin(tok(60),{action:'set',name:'cap',value:''});assert.equal(await linkAllows(env,{user:'a',item:'s3'}),'ok','back to the deployed default');
// immediate account ban and unban
const uid='11111111-2222-4333-8444-555555555555';
await admin(tok(60),{action:'ban-user',user:uid});assert.equal(await linkAllows(env,{user:uid,item:'s1'}),'limit','banned at once');
forgetBans();await admin(tok(60),{action:'unban-user',user:uid});assert.equal(await linkAllows(env,{user:uid,item:'s1'}),'ok','unbanned');
// network ban: every account on that network, also reopening
await linkAllows(env,{user:'b',item:'x1',ip:'203.0.113.9'});
await admin(tok(60),{action:'ban-net',ip:'203.0.113.9',hours:2});
assert.equal(await linkAllows(env,{user:'b',item:'x1',ip:'203.0.113.9'}),'limit','even an opened series');assert.equal(await linkAllows(env,{user:'c',item:'x2',ip:'203.0.113.9'}),'limit');
assert.equal(await linkAllows(env,{user:'c',item:'x2',ip:'198.51.100.1'}),'ok','other network fine');
assert.equal((await (await admin(tok(null))).json()).netBans[0].net,'203.0.113.9');
await admin(tok(60),{action:'unban-net',net:'203.0.113.9'});assert.equal(await linkAllows(env,{user:'c',item:'x3',ip:'203.0.113.9'}),'ok');
// hCaptcha emergency switch: off → box + picture enough; on again → hCaptcha needed
cdata='0123456789abcdef0123456789abcdef';
assert.equal(await humanOk(env,'tok-1234567890:q'+quizTarget(cdata),'',net),'','hCaptcha required');
await admin(tok(60),{action:'set',name:'hcaptcha',value:0});assert.equal(await humanOk(env,'tok-1234567890:q'+quizTarget(cdata),'',net),cdata,'switched off in an emergency');
await admin(tok(60),{action:'set',name:'hcaptcha',value:''});assert.equal(await humanOk(env,'tok-1234567890:q'+quizTarget(cdata),'',net),'','back on');
// 14/11: one account's activity (counts only) with GET ?user=; any other query refused
const getq=(q,t=tok(null))=>handle(new Request('https://respaldo.zzanime.uk/owner/admin'+q,{headers:{Authorization:'Bearer '+t}}),env,net);
const act='22222222-3333-4444-8555-666666666666';await linkAllows(env,{user:act,item:'p1'});await linkAllows(env,{user:act,item:'p2'});
let ua=await (await getq('?user='+act)).json();assert.equal(ua.today.series,2);assert.ok(Array.isArray(ua.days));assert.ok(!JSON.stringify(ua).includes('p1'),'never which series');
assert.equal((await getq('?user=../x')).status,400);assert.equal((await getq('?user='+act+'&x=1')).status,400);
isOwner=false;assert.equal((await getq('?user='+act)).status,403);isOwner=true;
// body limits
assert.equal((await admin(tok(60),{action:'set',name:'cap',value:5,pad:'x'.repeat(3000)})).status,413);
console.log('controles del dueño: solo dueño, código reciente, topes, baneo de cuenta y red, interruptor hCaptcha OK');
