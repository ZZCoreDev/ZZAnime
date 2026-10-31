// Playback probe: selection and day logic, plus a real headless run against local fake embeds.
import assert from 'node:assert/strict';import http from 'node:http';import {chromium} from 'playwright';
import {pick,merge,embed,FAMILIES,MAX_EMBEDS} from './select.mjs';
import {probeOne,serve} from './probe.mjs';
const ep=(n,at,options,extra)=>({url:'https://jkanime.net/s'+n+'/1/',observedAt:at,options,...(extra?{extraOptions:extra}:{})});
const o=(family,url)=>({family,name:family,url});
const eps=[ep(1,'2026-10-30',[o('streamwish','https://hgcloud.to/e/abcdefgh1234'),o('mega','https://mega.nz/file/AbCdEfGh#'+'k'.repeat(43))]),
 ep(2,'2026-10-31',[o('streamwish','https://hgcloud.to/e/zzzzzzzz1234'),o('mp4upload','https://www.mp4upload.com/embed-x.html')],[o('yourupload','https://www.yourupload.com/embed/abc')]),
 ep(3,'2026-10-29',[o('streamwish','https://hgcloud.to/e/yyyyyyyy1234')]),ep(4,'2026-10-28',[o('voe','https://voe.sx/e/abcdefgh')])];
const p=pick(eps);
assert.deepEqual(p.filter(x=>x.family==='streamwish').map(x=>x.episode),['https://jkanime.net/s2/1/','https://jkanime.net/s1/1/']);
assert.equal(p.find(x=>x.family==='streamwish').embed,'https://hanerix.com/e/zzzzzzzz1234');
assert.equal(p.find(x=>x.family==='mega').embed,'https://mega.nz/embed/AbCdEfGh#'+'k'.repeat(43));
assert.ok(p.some(x=>x.family==='yourupload'));assert.ok(p.length<=MAX_EMBEDS);assert.equal(embed({family:'voe',url:'http://x'}),null);
const day1=merge(null,[{family:'voe',state:'not-advancing'},{family:'voe',state:'error'},{family:'mega',state:'played'},{family:'vidhide',state:'blocked-from-github'}],'2026-11-01','t1');
assert.equal(day1.families.voe.state,'failed');assert.equal(day1.families.voe.failingDays,1);assert.equal(day1.families.mega.state,'ok');
assert.equal(day1.families.vidhide.state,'blocked');assert.equal(day1.families.vidhide.failingDays,0);assert.equal(day1.families.mp4upload.state,'no-sample');
assert.equal(merge(day1,[{family:'voe',state:'error'}],'2026-11-01','t1b').families.voe.failingDays,1,'same day does not count twice');
const day2=merge(day1,[{family:'voe',state:'error'},{family:'mega',state:'error'}],'2026-11-02','t2');
assert.equal(day2.families.voe.failingDays,2);assert.equal(day2.families.mega.failingDays,1);assert.equal(day2.families.mega.lastOkAt,'t1');
assert.equal(merge(day2,[{family:'voe',state:'played'}],'2026-11-03','t3').families.voe.failingDays,0);
assert.deepEqual(Object.keys(day1.families),FAMILIES);
// Real Chromium: a cross-origin embed whose <video> advances, one that never plays, one blocked page.
const fake=http.createServer((req,res)=>{
 if(req.url==='/e/blocked'){res.writeHead(403,{'content-type':'text/html'}).end('<title>Just a moment...</title>cf-chl');return;}
 const play=req.url==='/e/live';
 res.writeHead(200,{'content-type':'text/html'}).end(`<!doctype html><video id=v width=320 height=180 ${play?'':'src="/none.mp4"'}></video><script>
 ${play?`const c=document.createElement('canvas');c.width=64;c.height=36;const g=c.getContext('2d');setInterval(()=>{g.fillStyle='#'+Math.floor(Math.random()*4095).toString(16).padStart(3,'0');g.fillRect(0,0,64,36)},50);
 document.addEventListener('click',()=>{v.srcObject=c.captureStream(20);v.muted=true;v.play()});`:''}</script>`);
}).listen(0,'127.0.0.1');await new Promise(r=>fake.on('listening',r));
const base='http://localhost:'+fake.address().port,server=await serve(),origin='http://127.0.0.1:'+server.address().port;
process.env.PROBE_WAIT_MS='12000';
const browser=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required']});
const t=e=>({family:'x',episode:'e',url:base+e,embed:base+e});
const live=await probeOne(browser,origin,t('/e/live'));assert.equal(live.state,'played',JSON.stringify(live));assert.ok(live.advanced>3);
const dead=await probeOne(browser,origin,t('/e/dead'));assert.notEqual(dead.state,'played');
const blocked=await probeOne(browser,origin,t('/e/blocked'));assert.equal(blocked.state,'blocked-from-github',JSON.stringify(blocked));
await browser.close();server.close();fake.close();
console.log('playback probe controls PASS (selection, day logic, played/not-played/blocked in real Chromium)');
