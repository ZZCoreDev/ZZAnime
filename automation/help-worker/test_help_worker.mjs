// Help Worker rules with a real SQLite store, a really signed channel and a really encrypted MEGA name.
// No network: every provider, MEGA and channel request goes to local fakes.
import assert from 'node:assert/strict';
import {createCipheriv,generateKeyPairSync,randomBytes,sign} from 'node:crypto';
// node:sqlite needs Node >= 22.5; GitHub's ubuntu-24.04 default Node is older, so skip instead of breaking the chain.
let DatabaseSync;
try{({DatabaseSync}=await import('node:sqlite'));}catch{console.log('help Worker controls SKIPPED: node:sqlite needs Node >= 22.5 (found '+process.version+')');process.exit(0);}
import {handle,Store,family,nameVerdict,megaName,resetWanted,sha} from './logic.js';

const TR='https://jkanime.net/tokyo-revengers-santen-sensou-hen/5/',SBR='https://jkanime.net/steel-ball-run-jojo-no-kimyou-na-bouken/7/',OLD='https://jkanime.net/ao-ashi/3/';
const WANTED=[{url:TR,number:5,title:'Tokyo Revengers: Santen Sensou-hen'},{url:SBR,number:7,title:'Steel Ball Run: JoJo no Kimyou na Bouken'},{url:OLD,number:3,title:'Ao Ashi',renew:true}];
const {publicKey,privateKey}=generateKeyPairSync('rsa',{modulusLength:2048});
const b64u=b=>Buffer.from(b).toString('base64').replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
function sqlite(){const db=new DatabaseSync(':memory:');return {exec(q,...p){const s=db.prepare(q);if(/^\s*SELECT/i.test(q))return {toArray:()=>s.all(...p).map(r=>({...r}))};s.run(...p);return {toArray:()=>[]};}};}
function channel(wanted,createdAt){const payload=JSON.stringify({schema:1,sequence:1,createdAt,indexSha256:'0'.repeat(64),indexPath:'indexes/'+'0'.repeat(64)+'.bin',indexBytes:1,mode:'daily-new',...(wanted?{wanted}:{})});return JSON.stringify({payload,signature:sign('sha256',Buffer.from(payload),privateKey).toString('hex')});}
function megaFile(name,id='AbCd1234'){
 const k=randomBytes(32),aes=Buffer.alloc(16);for(let i=0;i<16;i++)aes[i]=k[i]^k[i+16];
 let plain=Buffer.from('MEGA'+JSON.stringify({n:name}));plain=Buffer.concat([plain,Buffer.alloc((16-plain.length%16)%16)]);
 const c=createCipheriv('aes-128-cbc',aes,Buffer.alloc(16));c.setAutoPadding(false);
 return {id,key:b64u(k),at:b64u(Buffer.concat([c.update(plain),c.final()])),url:'https://mega.nz/file/'+id+'#'+b64u(k)};
}
function setup({wanted=WANTED,age=60000,mega=[],pages={}}={}){
 const now=Date.parse('2026-10-31T00:00:00Z');resetWanted();
 const env={PUBLIC_KEY:publicKey.export({type:'spki',format:'der'}).toString('base64'),CHANNEL_URL:'https://channel.test/channel.json',SALT:'salt',HELP_KEY:'secret',IP_LIMIT:'3',DAILY_CAP:'1000'};
 const files=Object.fromEntries(mega.map(f=>[f.id,f.at]));
 const fetcher=async(url,init={})=>{
  if(url===env.CHANNEL_URL)return new Response(channel(wanted,new Date(now-age).toISOString()));
  if(url.startsWith('https://g.api.mega.co.nz/cs')){const id=JSON.parse(init.body)[0].p;return Response.json(files[id]?[{s:1,at:files[id]}]:[-9]);}
  if(pages[url])return new Response('<html><title>'+pages[url]+'</title></html>');
  return new Response('blocked',{status:403});};
 return {now,env,store:new Store(sqlite()),fetcher};
}
let n=0;
async function submit(t,items,{device,asn=3352,ip}={}){
 device=device||'device-'+String(++n).padStart(12,'0');
 const req=new Request('https://help.test/v1/submit',{method:'POST',body:JSON.stringify({schema:1,device,items})});
 Object.defineProperty(req,'cf',{value:{asn}});req.headers.set('cf-connecting-ip',ip||device);
 const r=await handle(req,t.env,t.store,{now:()=>t.now,fetch:t.fetcher});const body=await r.json();
 return {status:r.status,body,of:e=>body.items?.find(i=>i.episode===e)?.status};
}
const item=(episode,...urls)=>({episode,options:urls.map(u=>({name:u.includes('mega')?'Mega':u.includes('vidhide')?'Vidhide':u.includes('mp4upload')?'Mp4upload':'Streamwish',url:u}))});
async function accepted(t,key='secret'){const r=await handle(new Request('https://help.test/v1/accepted',{headers:{authorization:'Bearer '+key}}),t.env,t.store,{now:()=>t.now+1000,fetch:t.fetcher});return {status:r.status,body:await r.json()};}
let passed=0;const check=async(name,fn)=>{await fn();passed++;};

await check('family mirrors the app policy',()=>{
 assert.equal(family('Mega'),'mega');assert.equal(family('Streamtape 2'),'streamtape');assert.equal(family('Streamwish'),'streamwish');assert.equal(family('Voe'),'');assert.equal(family('Megaupload'),'');});
await check('file name verdicts',()=>{
 assert.equal(nameVerdict('[Sub] Tokyo Revengers - Santen Sensou-hen - 05 [1080p].mp4',WANTED[0]),'match');
 assert.equal(nameVerdict('TokyoRevengers_SantenSensouhen_E05.mp4',WANTED[0]),'match');
 assert.equal(nameVerdict('Tokyo Revengers Santen Sensou-hen 06.mp4',WANTED[0]),'mismatch');
 assert.equal(nameVerdict('Steel Ball Run 07 [720p].mkv',WANTED[1]),'match');
 assert.equal(nameVerdict('One Piece 1150.mp4',WANTED[0]),'unknown');});
await check('real MEGA attribute decryption',async()=>{
 const f=megaFile('[Sub] Tokyo Revengers Santen Sensou-hen 05.mp4'),t=setup({mega:[f]});
 assert.equal(await megaName(f.url,t.fetcher),'[Sub] Tokyo Revengers Santen Sensou-hen 05.mp4');
 assert.equal(await megaName(f.url.replace('/file/','/embed/'),t.fetcher),'[Sub] Tokyo Revengers Santen Sensou-hen 05.mp4');
 assert.equal(await megaName(f.url.replace(f.id,'ZZZZ9999'),t.fetcher),null);});
await check('not wanted is told to stop; stale or unsigned channel asks for nothing',async()=>{
 const t=setup(),r=await submit(t,[item('https://jkanime.net/otra-serie/1/','https://www.mp4upload.com/embed-x.html'),item(TR,'https://www.mp4upload.com/embed-x.html')]);
 assert.equal(r.status,200);assert.equal(r.of('https://jkanime.net/otra-serie/1/'),'stop');assert.equal(r.of(TR),'stored');
 for(const s of [setup({age:2*86400000}),setup({wanted:null})])assert.equal((await submit(s,[item(TR,'https://www.mp4upload.com/embed-x.html')])).of(TR),'stop');
 const u=setup();u.env.PUBLIC_KEY=generateKeyPairSync('rsa',{modulusLength:2048}).publicKey.export({type:'spki',format:'der'}).toString('base64');
 await assert.rejects(submit(u,[item(TR,'https://www.mp4upload.com/embed-x.html')]),/channel signature/);});
await check('two devices on one network are not enough; two networks plus MEGA name are',async()=>{
 const f=megaFile('Tokyo Revengers Santen Sensou-hen 05.mp4'),t=setup({mega:[f]});
 await submit(t,[item(TR,f.url)],{asn:3352});await submit(t,[item(TR,f.url)],{asn:3352});
 assert.deepEqual((await accepted(t)).body.episodes,[]);
 await submit(t,[item(TR,f.url)],{asn:12479});
 const a=(await accepted(t)).body;assert.equal(a.episodes.length,1);const o=a.episodes[0].options[0];
 assert.deepEqual([a.episodes[0].url,o.check,o.devices,o.asns,a.episodes[0].acceptedAt],[TR,'name-match',3,2,'2026-10-31T00:00:00.000Z']);});
await check('valid MEGA link of another video is rejected even with quorum',async()=>{
 const f=megaFile('Random Video 05.mp4'),t=setup({mega:[f]});
 for(const asn of [1,2,3])await submit(t,[item(TR,f.url)],{asn});
 assert.deepEqual((await accepted(t)).body.episodes,[]);});
await check('readable title of another video is rejected; unreadable or generic needs three networks',async()=>{
 const t=setup({pages:{'https://streamwish.to/e/other':'Tokyo Revengers Santen Sensou-hen 04','https://streamwish.to/e/wrong':'Steel Ball Run 08.mp4','https://vidhide.to/e/generic':'Watch video','https://vidhide.to/e/named':'Steel_Ball_Run_07.mp4'}});
 const urls=['https://streamwish.to/e/ok','https://streamwish.to/e/other','https://streamwish.to/e/wrong','https://vidhide.to/e/generic','https://vidhide.to/e/named'];
 for(const asn of [1,2])await submit(t,[item(SBR,...urls)],{asn});
 assert.deepEqual((await accepted(t)).body.episodes[0].options.map(o=>[o.url,o.check]),[['https://vidhide.to/e/named','name-match']]);
 await submit(t,[item(SBR,...urls)],{asn:3});
 const opts=(await accepted(t)).body.episodes[0].options.map(o=>[o.url,o.check]).sort();
 assert.deepEqual(opts,[['https://streamwish.to/e/ok','quorum3'],['https://vidhide.to/e/generic','quorum3'],['https://vidhide.to/e/named','name-match']]);});
await check('enough accepted options stop further work on that chapter',async()=>{
 const a=megaFile('Tokyo Revengers Santen Sensou-hen 05.mp4','AAAA1111'),b=megaFile('[HD] Tokyo Revengers Santen Sensouhen 05.mp4','BBBB2222'),t=setup({mega:[a,b]});
 for(const asn of [1,2])await submit(t,[item(TR,a.url,b.url)],{asn});
 assert.equal((await accepted(t)).body.episodes[0].options.length,2);
 assert.equal((await submit(t,[item(TR,a.url,b.url)],{asn:3})).of(TR),'enough');});
await check('renewal entries are batched and flagged back to the cloud',async()=>{
 const f=megaFile('Ao Ashi - 03.mp4','CCCC3333'),g=megaFile('Tokyo Revengers Santen Sensou-hen 05.mp4','DDDD4444'),t=setup({mega:[f,g]});
 for(const asn of [7,8]){const r=await submit(t,[item(OLD,f.url),item(TR,g.url)],{asn});assert.equal(r.of(OLD),'stored');assert.equal(r.of(TR),'stored');}
 const eps=(await accepted(t)).body.episodes,old=eps.find(e=>e.url===OLD);
 assert.equal(eps.length,2);assert.equal(old.renew,true);assert.equal(eps.find(e=>e.url===TR).renew,undefined);});
await check('repeat answers from one device count once',async()=>{
 const f=megaFile('Tokyo Revengers Santen Sensou-hen 05.mp4'),t=setup({mega:[f]});
 assert.equal((await submit(t,[item(TR,f.url)],{device:'device-same-device-1',asn:1})).of(TR),'stored');
 assert.equal((await submit(t,[item(TR,f.url)],{device:'device-same-device-1',asn:2,ip:'other'})).of(TR),'duplicate');
 assert.deepEqual((await accepted(t)).body.episodes,[]);});
await check('per-IP daily limit, unsupported options, missing network and auth',async()=>{
 const t=setup(),opt=item(TR,'https://www.mp4upload.com/embed-x.html');
 for(let i=0;i<3;i++)assert.equal((await submit(t,[opt],{ip:'1.1.1.1'})).status,200);
 assert.equal((await submit(t,[opt],{ip:'1.1.1.1'})).status,429);
 assert.equal((await submit(t,[{episode:TR,options:[{name:'Voe',url:'https://voe.sx/e/x'}]}])).of(TR),'unsupported');
 assert.equal((await submit(t,[opt],{asn:0})).status,400);
 assert.equal((await submit(t,Array.from({length:21},()=>opt))).status,400);
 assert.equal((await accepted(t,'wrong')).status,401);});
await check('no clear identifiers are stored',async()=>{
 const t=setup();await submit(t,[item(TR,'https://www.mp4upload.com/embed-x.html')],{device:'device-eeeeeeeeeeee1',ip:'203.0.113.7'});
 const dump=JSON.stringify(t.store.rows('SELECT * FROM seen'))+JSON.stringify(t.store.rows('SELECT * FROM counters'));
 assert.ok(!dump.includes('device-eeeeeeeeeeee1')&&!dump.includes('203.0.113.7'));assert.ok(dump.includes(await sha('salt|device|device-eeeeeeeeeeee1')));});
await check('chapter filled in the channel is forgotten and told to stop',async()=>{
 const f=megaFile('Tokyo Revengers Santen Sensou-hen 05.mp4'),t=setup({mega:[f]});
 for(const asn of [1,2])await submit(t,[item(TR,f.url)],{asn});
 assert.equal((await accepted(t)).body.episodes.length,1);
 const after=setup({wanted:[WANTED[1]],mega:[f]});after.store=t.store;
 assert.deepEqual((await accepted(after)).body.episodes,[]);assert.equal(t.store.rows('SELECT * FROM seen WHERE episode=?',TR).length,0);
 assert.equal((await submit(after,[item(TR,f.url)],{asn:3})).of(TR),'stop');});
console.log(passed+' help Worker controls PASS (signed wanted list, batches, two networks, MEGA name, enough, renewal, limits, privacy, stop when filled)');
