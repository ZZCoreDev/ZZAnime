// Help Worker rules with a real SQLite store, a really signed channel and a really encrypted MEGA name.
// No network: every provider, MEGA and channel request goes to local fakes.
import assert from 'node:assert/strict';
import {createCipheriv,generateKeyPairSync,randomBytes,sign} from 'node:crypto';
// node:sqlite needs Node >= 22.5; GitHub's ubuntu-24.04 default Node is older, so skip instead of breaking the chain.
let DatabaseSync;
try{({DatabaseSync}=await import('node:sqlite'));}catch{console.log('help Worker controls SKIPPED: node:sqlite needs Node >= 22.5 (found '+process.version+')');process.exit(0);}
import {handle,Store,family,nameVerdict,megaName,resetWanted,sha} from './logic.js';

const TR='https://jkanime.net/tokyo-revengers-santen-sensou-hen/5/',SBR='https://jkanime.net/steel-ball-run-jojo-no-kimyou-na-bouken/7/';
const WANTED=[{url:TR,number:5,title:'Tokyo Revengers: Santen Sensou-hen'},{url:SBR,number:7,title:'Steel Ball Run: JoJo no Kimyou na Bouken'}];
const {publicKey,privateKey}=generateKeyPairSync('rsa',{modulusLength:2048});
const b64u=b=>Buffer.from(b).toString('base64').replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
function sqlite(){const db=new DatabaseSync(':memory:');return {exec(q,...p){const s=db.prepare(q);if(/^\s*SELECT/i.test(q))return {toArray:()=>s.all(...p).map(r=>({...r}))};s.run(...p);return {toArray:()=>[]};}};}
function channel(wanted,createdAt){const payload=JSON.stringify({schema:1,sequence:1,createdAt,indexSha256:'0'.repeat(64),indexPath:'indexes/'+'0'.repeat(64)+'.bin',indexBytes:1,mode:'daily-new',...(wanted?{wanted}:{})});return JSON.stringify({payload,signature:sign('sha256',Buffer.from(payload),privateKey).toString('hex')});}
function megaFile(name){
 const k=randomBytes(32),aes=Buffer.alloc(16);for(let i=0;i<16;i++)aes[i]=k[i]^k[i+16];
 let plain=Buffer.from('MEGA'+JSON.stringify({n:name}));plain=Buffer.concat([plain,Buffer.alloc((16-plain.length%16)%16)]);
 const c=createCipheriv('aes-128-cbc',aes,Buffer.alloc(16));c.setAutoPadding(false);
 return {id:'AbCd1234',key:b64u(k),at:b64u(Buffer.concat([c.update(plain),c.final()]))};
}
function setup({wanted=WANTED,age=60000,mega={},pages={}}={}){
 const now=Date.parse('2026-10-31T00:00:00Z');resetWanted();
 const env={PUBLIC_KEY:publicKey.export({type:'spki',format:'der'}).toString('base64'),CHANNEL_URL:'https://channel.test/channel.json',SALT:'salt',HELP_KEY:'secret',IP_LIMIT:'3',DAILY_CAP:'1000'};
 const calls=[];
 const fetcher=async(url,init={})=>{calls.push(url);
  if(url===env.CHANNEL_URL)return new Response(channel(wanted,new Date(now-age).toISOString()));
  if(url.startsWith('https://g.api.mega.co.nz/cs')){const id=JSON.parse(init.body)[0].p;return Response.json(mega[id]?[{s:1,at:mega[id]}]:[-9]);}
  if(pages[url])return new Response('<html><title>'+pages[url]+'</title></html>');
  return new Response('blocked',{status:403});};
 return {now,env,store:new Store(sqlite()),fetcher,calls};
}
async function submit(t,episode,options,{device='device-aaaaaaaaaaaa1',asn=3352,ip='1.1.1.1'}={}){
 const req=new Request('https://help.test/v1/submit',{method:'POST',body:JSON.stringify({schema:1,episode,device,options})});
 Object.defineProperty(req,'cf',{value:{asn}});req.headers.set('cf-connecting-ip',ip);
 const r=await handle(req,t.env,t.store,{now:()=>t.now,fetch:t.fetcher});return {status:r.status,body:await r.json()};
}
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
 const f=megaFile('[Sub] Tokyo Revengers Santen Sensou-hen 05.mp4'),t=setup({mega:{[f.id]:f.at}});
 assert.equal(await megaName('https://mega.nz/file/'+f.id+'#'+f.key,t.fetcher),'[Sub] Tokyo Revengers Santen Sensou-hen 05.mp4');
 assert.equal(await megaName('https://mega.nz/embed/'+f.id+'#'+f.key,t.fetcher),'[Sub] Tokyo Revengers Santen Sensou-hen 05.mp4');
 assert.equal(await megaName('https://mega.nz/file/ZZZZ9999#'+f.key,t.fetcher),null);});
await check('not wanted is refused and told to stop',async()=>{
 const t=setup(),r=await submit(t,'https://jkanime.net/otra-serie/1/',[{name:'Mega',url:'https://mega.nz/file/AbCd1234#'+'k'.repeat(43)}]);
 assert.equal(r.status,409);assert.equal(r.body.stop,true);});
await check('stale, unsigned or empty channel asks for nothing',async()=>{
 for(const t of [setup({age:2*86400000}),setup({wanted:null})])assert.equal((await submit(t,TR,[{name:'Mega',url:'https://mega.nz/x/'}])).status,409);
 const t=setup();t.env.PUBLIC_KEY=generateKeyPairSync('rsa',{modulusLength:2048}).publicKey.export({type:'spki',format:'der'}).toString('base64');
 await assert.rejects(submit(t,TR,[{name:'Mega',url:'https://mega.nz/x/'}]),/channel signature/);});
await check('two devices on one network are not enough; two networks plus name match are',async()=>{
 const f=megaFile('Tokyo Revengers Santen Sensou-hen 05.mp4'),t=setup({mega:{[f.id]:f.at}}),opt=[{name:'Mega',url:'https://mega.nz/file/'+f.id+'#'+f.key}];
 assert.equal((await submit(t,TR,opt,{device:'device-aaaaaaaaaaaa1',asn:3352,ip:'1.1.1.1'})).body.accepted,true);
 assert.equal((await submit(t,TR,opt,{device:'device-aaaaaaaaaaaa2',asn:3352,ip:'1.1.1.2'})).body.accepted,true);
 assert.deepEqual((await accepted(t)).body.episodes,[]);
 await submit(t,TR,opt,{device:'device-aaaaaaaaaaaa3',asn:12479,ip:'2.2.2.2'});
 const a=(await accepted(t)).body;assert.equal(a.episodes.length,1);const o=a.episodes[0].options[0];
 assert.equal(a.episodes[0].url,TR);assert.equal(o.check,'name-match');assert.equal(o.devices,3);assert.equal(o.asns,2);assert.equal(a.episodes[0].acceptedAt,'2026-10-31T00:00:00.000Z');});
await check('valid MEGA link of another video is rejected even with quorum',async()=>{
 const f=megaFile('Random Video 05.mp4'),t=setup({mega:{[f.id]:f.at}}),opt=[{name:'Mega',url:'https://mega.nz/file/'+f.id+'#'+f.key}];
 for(const [d,asn] of [['device-bbbbbbbbbbbb1',1],['device-bbbbbbbbbbbb2',2],['device-bbbbbbbbbbbb3',3]])await submit(t,TR,opt,{device:d,asn,ip:d});
 assert.deepEqual((await accepted(t)).body.episodes,[]);});
await check('unreadable provider needs three networks; wrong title is rejected',async()=>{
 const t=setup({pages:{'https://streamwish.to/e/other':'Tokyo Revengers Santen Sensou-hen 04','https://streamwish.to/e/wrong':'Steel Ball Run 08.mp4','https://vidhide.to/e/generic':'Watch video','https://vidhide.to/e/named':'Steel_Ball_Run_07.mp4'}});
 const sets=['https://streamwish.to/e/ok','https://streamwish.to/e/other','https://streamwish.to/e/wrong','https://vidhide.to/e/generic','https://vidhide.to/e/named'].map(u=>[{name:u.includes('vidhide')?'Vidhide':'Streamwish',url:u}]);
 for(const [d,asn] of [['device-cccccccccccc1',1],['device-cccccccccccc2',2]])for(const o of sets)await submit(t,SBR,o,{device:d,asn,ip:d+o[0].url});
 assert.deepEqual((await accepted(t)).body.episodes[0].options.map(o=>[o.url,o.check]),[['https://vidhide.to/e/named','name-match']]);
 for(const o of sets)await submit(t,SBR,o,{device:'device-cccccccccccc3',asn:3,ip:'x'+o[0].url});
 t.now+=7*3600000;// past the 6 h check cache
 const opts=(await accepted(t)).body.episodes[0].options.map(o=>[o.url,o.check]).sort();
 assert.deepEqual(opts,[['https://streamwish.to/e/ok','quorum3'],['https://vidhide.to/e/generic','quorum3'],['https://vidhide.to/e/named','name-match']]);});
await check('per-IP daily limit, unsupported options and auth',async()=>{
 const t=setup(),opt=[{name:'Mp4upload',url:'https://www.mp4upload.com/embed-x.html'}];
 for(let i=0;i<3;i++)assert.equal((await submit(t,TR,opt,{device:'device-dddddddddddd'+i})).status,200);
 assert.equal((await submit(t,TR,opt,{device:'device-dddddddddddd9'})).status,429);
 assert.equal((await submit(t,TR,[{name:'Voe',url:'https://voe.sx/e/x'}],{ip:'9.9.9.9'})).status,422);
 assert.equal((await submit(t,TR,opt,{asn:0,ip:'8.8.8.8'})).status,400);
 assert.equal((await accepted(t,'wrong')).status,401);});
await check('no clear identifiers are stored',async()=>{
 const t=setup();await submit(t,TR,[{name:'Mp4upload',url:'https://www.mp4upload.com/embed-x.html'}],{device:'device-eeeeeeeeeeee1',ip:'203.0.113.7'});
 const dump=JSON.stringify(t.store.sql.exec('SELECT * FROM submissions').toArray())+JSON.stringify(t.store.sql.exec('SELECT * FROM counters').toArray());
 assert.ok(!dump.includes('device-eeeeeeeeeeee1')&&!dump.includes('203.0.113.7'));assert.ok(dump.includes(await sha('salt|device|device-eeeeeeeeeeee1')));});
await check('chapter filled in the channel stops being accepted',async()=>{
 const f=megaFile('Tokyo Revengers Santen Sensou-hen 05.mp4'),t=setup({mega:{[f.id]:f.at}}),opt=[{name:'Mega',url:'https://mega.nz/file/'+f.id+'#'+f.key}];
 await submit(t,TR,opt,{device:'device-ffffffffffff1',asn:1,ip:'a'});await submit(t,TR,opt,{device:'device-ffffffffffff2',asn:2,ip:'b'});
 assert.equal((await accepted(t)).body.episodes.length,1);
 const after=setup({wanted:[WANTED[1]],mega:{[f.id]:f.at}});after.store=t.store;
 assert.deepEqual((await accepted(after)).body.episodes,[]);assert.equal((await submit(after,TR,opt,{device:'device-ffffffffffff3',asn:3,ip:'c'})).status,409);});
console.log(passed+' help Worker controls PASS (signed wanted list, two networks, MEGA name, limits, privacy, stop when filled)');
