// Offline security regressions: SQLite is real, every network request is a fake.
import assert from 'node:assert/strict';
import test from 'node:test';
import {DatabaseSync} from 'node:sqlite';
import {generateKeyPairSync,sign} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {handle,Store,inspect,resetWanted,sha} from './logic.js';
import {SUBMIT_HOSTS,SUBMIT_POLICY_VERSION,submitUrlAllowed} from './submit-policy.js';
import {boundedText,InspectionPolicyError} from './bounded-fetch.js';

globalThis.fetch=()=>{throw new Error('Real network forbidden in security tests');};
const NOW=Date.parse('2026-11-02T12:00:00Z'),EP='https://jkanime.net/tokyo-revengers-santen-sensou-hen/5/';
const ENTRY={url:EP,number:5,title:'Tokyo Revengers Santen Sensou-hen'};
const GOOD='https://www.mp4upload.com/embed-good1234.html';
const TITLE='<title>Tokyo Revengers Santen Sensou-hen 05</title>';
const {publicKey,privateKey}=generateKeyPairSync('rsa',{modulusLength:2048});
function sqlite(db){return{exec(q,...p){const s=db.prepare(q);if(/^\s*SELECT/i.test(q))return{toArray:()=>s.all(...p).map(r=>({...r}))};s.run(...p);return{toArray:()=>[]};}};}
function setup(fetcher=async()=>new Response(TITLE)){
 resetWanted();const db=new DatabaseSync(':memory:');
 const store=new Store(sqlite(db));
 const env={SALT:'synthetic-salt',HELP_KEY:'synthetic-key',PUBLIC_KEY:publicKey.export({type:'spki',format:'der'}).toString('base64'),CHANNEL_URL:'https://channel.invalid/channel.json',IP_LIMIT:'200',DAILY_CAP:'40000'};
 const calls=[];const fetch=async(url,init)=>{calls.push({url,init});if(url===env.CHANNEL_URL){const payload=JSON.stringify({schema:1,createdAt:new Date(NOW).toISOString(),wanted:[ENTRY]});return Response.json({payload,signature:sign('sha256',Buffer.from(payload),privateKey).toString('hex')});}return fetcher(url,init);};
 return{store,env,fetch,calls,db};
}
async function submit(t,urls,device='synthetic-client-0001',asn=64500){
 const req=new Request('https://help.invalid/v1/submit',{method:'POST',body:JSON.stringify({schema:1,device,items:[{episode:EP,options:urls.map(url=>({name:'Mp4upload',url}))}]})});
 Object.defineProperty(req,'cf',{value:{asn}});req.headers.set('cf-connecting-ip','203.0.113.'+(asn-64499));
 const r=await handle(req,t.env,t.store,{now:()=>NOW,fetch:t.fetch});assert.equal(r.status,200);return r.json();
}
async function accepted(t){const r=await handle(new Request('https://help.invalid/v1/accepted',{headers:{authorization:'Bearer '+t.env.HELP_KEY}}),t.env,t.store,{now:()=>NOW,fetch:t.fetch});return(await r.json()).episodes;}
const option=url=>({name:'Mp4upload',family:'mp4upload',url});

test('foreign hosts and cross-family URLs are rejected before storage or provider requests',async()=>{
 for(const bad of ['https://attacker.invalid/p','https://mega.nz/p','https://mp4upload.com.attacker.invalid/p','https://mp4upload.com:443/p','https://user@mp4upload.com/p','https://mp4upload.com./p','https://.mp4upload.com/p','https://-bad.mp4upload.com/p','https://bad-.mp4upload.com/p','https://bad..mp4upload.com/p','https://MP4UPLOAD.COM/p','https://SUB.mp4upload.com/p','https://mp4upload.com/\\path','https://mp4upload.com/\npath','https://mp4upload.com/<x>','https://mp4upload.com/%xx']){
  const t=setup();const response=await submit(t,[bad]);assert.equal(response.items[0].status,'unsupported',bad);
  assert.equal(t.store.rows('SELECT * FROM seen').length,0);assert.equal(t.calls.filter(c=>c.url!==t.env.CHANNEL_URL).length,0);
 }
});
test('allowed provider remains functional with manual redirects',async()=>{
 const t=setup();await submit(t,[GOOD]);await submit(t,[GOOD],'synthetic-client-0002',64501);
 assert.equal((await accepted(t))[0].options[0].url,GOOD);
 assert.equal(t.calls.find(c=>c.url===GOOD).init.redirect,'manual');
});
test('a prohibited redirect is terminal and never promoted by three networks',async()=>{
 const t=setup(async()=>new Response(null,{status:302,headers:{location:'https://attacker.invalid/p'}}));
 for(let i=0;i<3;i++)await submit(t,[GOOD],'synthetic-client-000'+(i+1),64500+i);
 assert.deepEqual(await accepted(t),[]);assert.ok(t.calls.every(c=>c.url!== 'https://attacker.invalid/p'));
});
test('oversized provider response is cancelled and cannot become quorum3',async()=>{
 let cancelled=0;
 const t=setup(async()=>new Response(new ReadableStream({start(c){c.enqueue(new TextEncoder().encode(TITLE));c.enqueue(new Uint8Array(262145));c.enqueue(new Uint8Array(1));c.close();},cancel(){cancelled++;}})));
 for(let i=0;i<3;i++)await submit(t,[GOOD],'synthetic-client-000'+(i+1),64500+i);
 assert.deepEqual(await accepted(t),[]);assert.ok(cancelled>=1);
});
test('old accepted decisions neither export nor stop new submissions; records are retained',async()=>{
 const t=setup();const old=['https://attacker.invalid/a','https://attacker.invalid/b'];
 for(const url of old)t.store.sql.exec('INSERT INTO decided(episode,okey,name,family,url,devices,asns,first,verdict,checked,zones) VALUES(?,?,?,?,?,?,?,?,?,?,?)',EP,await sha('Mp4upload\0'+url),'Mp4upload','mp4upload',url,2,2,NOW,'name-match',NOW,0);
 assert.deepEqual(await accepted(t),[]);assert.notEqual((await submit(t,[GOOD])).items[0].status,'enough');
 assert.equal(t.store.rows('SELECT * FROM decided').length,2);
});
test('old allowed-host decisions require fresh policy inspection despite previous acceptance',async()=>{
 const t=setup();const key=await sha('Mp4upload\0'+GOOD);
 for(let i=0;i<2;i++)t.store.sql.exec('INSERT INTO seen(episode,device,asn,created,options,zone) VALUES(?,?,?,?,?,?)',EP,'old-device-'+i,64500+i,NOW,JSON.stringify([{okey:key,...option(GOOD)}]),'zone-'+i);
 t.store.sql.exec('INSERT INTO decided(episode,okey,name,family,url,devices,asns,first,verdict,checked,zones) VALUES(?,?,?,?,?,?,?,?,?,?,?)',EP,key,'Mp4upload','mp4upload',GOOD,2,2,NOW,'name-match',NOW,2);
 assert.deepEqual(await accepted(t),[]);await submit(t,[GOOD]);assert.ok(t.calls.some(c=>c.url===GOOD));
 assert.equal((await accepted(t))[0].options[0].url,GOOD);
});
test('direct inspections refuse untrusted URLs before fetch',async()=>{
 let calls=0;const r=await inspect(option('https://attacker.invalid/p'),ENTRY,async()=>{calls++;return new Response(TITLE)});
 assert.equal(r.verdict,'policy-rejected');assert.equal(calls,0);
});
test('host policy matches the checked-in Java intersection for every family',()=>{
 const java=readFileSync(new URL('../hourly/java/AnimeFlvSource.java',import.meta.url),'utf8');
 const policy=readFileSync(new URL('../hourly/java/ProviderPlaybackPolicy.java',import.meta.url),'utf8');
 const strings=s=>[...s.matchAll(/"([^"]+)"/g)].map(m=>m[1]);
 const embeds=strings(java.match(/EMBED_HOSTS=\{([^}]+)\}/)[1]);
 const groups=[...java.match(/SCOPED_FAMILIES=\{(.+?)\};/)[1].matchAll(/\{([^}]+)\}/g)].map(m=>strings(m[1]));
 const expected={};
 for(const [,f,host] of policy.matchAll(/case "([^"]+)":return "https:\/\/([^/]+)\/";/g)){
  expected[f]=(groups.find(g=>g.includes(host))||[]).filter(h=>embeds.some(root=>h===root||h.endsWith('.'+root)));
 }
 assert.deepEqual(SUBMIT_HOSTS,expected);
 for(const [f,hosts] of Object.entries(expected))for(const host of hosts){assert.ok(submitUrlAllowed(f,'https://'+host+'/embed'));assert.ok(submitUrlAllowed(f,'https://sub.'+host+'/embed'));}
 for(const f of ['desu','magi','voe'])assert.equal(submitUrlAllowed(f,'https://mega.nz/embed'),false);
 for(const u of ['https://static.mega.co.nz/embed','https://mega.co.nz/embed'])assert.equal(submitUrlAllowed('mega',u),false);
});
test('same-family relative and mirror redirects work, foreign redirect hops are never requested',async()=>{
 const calls=[];
 const result=await boundedText('https://streamwish.to/e/a',{},async(url,init)=>{
  calls.push(url);assert.equal(init.redirect,'manual');
  if(url.endsWith('/a'))return new Response(null,{status:302,headers:{location:'/e/b'}});
  if(url.endsWith('/b'))return new Response(null,{status:307,headers:{location:'https://hanerix.com/e/c'}});
  return new Response(TITLE);
 },u=>submitUrlAllowed('streamwish',u));
 assert.equal(result,TITLE);assert.equal(calls.length,3);
 for(const location of ['https://attacker.invalid/x','//mp4upload.com:443/x','http://mp4upload.com/x','https://user@mp4upload.com/x']){
  let n=0;await assert.rejects(boundedText(GOOD,{},async()=>{n++;return new Response(null,{status:302,headers:{location}})},u=>submitUrlAllowed('mp4upload',u)),InspectionPolicyError);assert.equal(n,1);
 }
});
test('redirect loops are bounded and all bodies are cancelled',async()=>{
 let n=0,cancelled=0;
 await assert.rejects(boundedText(GOOD,{},async()=>{n++;return new Response(new ReadableStream({cancel(){cancelled++;}}),{status:302,headers:{location:GOOD}})},u=>submitUrlAllowed('mp4upload',u)),InspectionPolicyError);
 assert.equal(n,4);assert.equal(cancelled,4);
});
test('the deadline covers stalled headers and bodies, including late response cleanup',async()=>{
 let cancelled=0;
 await assert.rejects(boundedText(GOOD,{},async()=>new Response(new ReadableStream({cancel(){cancelled++;}})),()=>true,{timeoutMs:20}),/inspection-timeout/);
 assert.equal(cancelled,1);
 await assert.rejects(boundedText(GOOD,{},()=>new Promise(resolve=>setTimeout(()=>resolve(new Response(new ReadableStream({cancel(){cancelled++;}}))),40)),()=>true,{timeoutMs:10}),/inspection-timeout/);
 await new Promise(r=>setTimeout(r,50));assert.equal(cancelled,2);
});
test('a false short Content-Length does not bypass the streaming limit',async()=>{
 let cancelled=0;
 await assert.rejects(boundedText(GOOD,{},async()=>new Response(new ReadableStream({start(c){c.enqueue(new Uint8Array(33));},cancel(){cancelled++;}}),{headers:{'content-length':'1'}}),()=>true,{maxBytes:32}),InspectionPolicyError);
 assert.equal(cancelled,1);
});
test('MEGA inspection has bounded body reads and refuses API redirects',async()=>{
 const o={name:'Mega',family:'mega',url:'https://mega.nz/file/AbCd1234#'+'A'.repeat(43)};
 const calls=[];const verdict=await inspect(o,ENTRY,async(url,init)=>{calls.push(url);assert.equal(init.redirect,'manual');assert.ok(init.signal);return new Response(null,{status:302,headers:{location:'https://attacker.invalid/'}});});
 assert.equal(calls.length,1);assert.ok(calls[0].startsWith('https://g.api.mega.co.nz/cs?id='));assert.equal(verdict.verdict,'policy-rejected');
 const big=await inspect(o,ENTRY,async()=>new Response('x'.repeat(16385)));assert.equal(big.verdict,'policy-rejected');
});
test('old rows survive migration and current-policy invalid rows cannot trigger enough',async()=>{
 const t=setup();
 for(const suffix of ['a','b'])t.store.sql.exec('INSERT INTO decided(episode,okey,name,family,url,devices,asns,first,verdict,checked,zones,policy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',EP,'old-'+suffix,'Mp4upload','mp4upload','https://attacker.invalid/'+suffix,2,2,NOW,'name-match',NOW,0,SUBMIT_POLICY_VERSION);
 assert.deepEqual(await accepted(t),[]);assert.equal((await submit(t,[GOOD])).items[0].status,'stored');assert.equal(t.store.rows('SELECT * FROM decided').length,2);
});
test('initialization and reopening preserve legacy tables and add policy without discarding rows',()=>{
 const db=new DatabaseSync(':memory:');
 db.exec("CREATE TABLE submissions(evidence TEXT);INSERT INTO submissions VALUES('preserve-submission');CREATE TABLE checks(evidence TEXT);INSERT INTO checks VALUES('preserve-check');CREATE TABLE decided(episode TEXT,okey TEXT,name TEXT,family TEXT,url TEXT,devices INTEGER,asns INTEGER,first INTEGER,verdict TEXT,checked INTEGER,PRIMARY KEY(episode,okey));");
 db.prepare('INSERT INTO decided VALUES(?,?,?,?,?,?,?,?,?,?)').run(EP,'old-key','Mp4upload','mp4upload',GOOD,2,2,NOW,'name-match',NOW);
 for(let i=0;i<2;i++){
  const store=new Store(sqlite(db));
  assert.equal(store.rows('SELECT * FROM submissions')[0].evidence,'preserve-submission');
  assert.equal(store.rows('SELECT * FROM checks')[0].evidence,'preserve-check');
  const rows=store.rows('SELECT * FROM decided');assert.equal(rows.length,1);assert.equal(rows[0].policy,'');assert.equal(rows[0].url,GOOD);
 }
});
