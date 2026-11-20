// Playback probe: selection and day logic, plus a real headless run against local fake embeds.
import assert from 'node:assert/strict';import http from 'node:http';import {chromium} from 'playwright';
import {pick,merge,embed,schedule,FAMILIES,MAX_EMBEDS} from './select.mjs';
import fs from 'node:fs';
process.env.PROBE_WAIT_MS ||= '12000';
const {probeOne,serve}=await import('./probe.mjs');
const ep=(n,at,options,extra)=>({url:'https://jkanime.net/s'+n+'/1/',observedAt:at,options,...(extra?{extraOptions:extra}:{})});
const o=(family,url)=>({family,name:family,url});
const eps=[ep(1,'2026-10-30',[o('streamwish','https://hgcloud.to/e/abcdefgh1234'),o('mega','https://mega.nz/file/AbCdEfGh#'+'k'.repeat(43))]),
 ep(2,'2026-10-31',[o('streamwish','https://hgcloud.to/e/zzzzzzzz1234'),o('mp4upload','https://www.mp4upload.com/embed-x.html')],[o('yourupload','https://www.yourupload.com/embed/abc')]),
 ep(3,'2026-10-29',[o('streamwish','https://hgcloud.to/e/yyyyyyyy1234')]),ep(4,'2026-10-28',[o('voe','https://voe.sx/e/abcdefgh')])];
const p=pick(eps);
assert.deepEqual(p.filter(x=>x.family==='streamwish').map(x=>x.episode),['https://jkanime.net/s2/1/','https://jkanime.net/s1/1/','https://jkanime.net/s3/1/']);
assert.equal(p.find(x=>x.family==='streamwish').embed,'https://hanerix.com/e/zzzzzzzz1234');
assert.equal(p.find(x=>x.family==='mega').embed,'https://mega.nz/embed/AbCdEfGh#'+'k'.repeat(43));
assert.ok(p.some(x=>x.family==='yourupload'));
// Round 1: one per family; retries only for families that have not played; never more than 12.
const many=FAMILIES.flatMap(f=>[0,1,2,3,4].map(i=>({family:f,episode:f+i})));
const order=[...schedule(many,new Set())];assert.equal(order.length,MAX_EMBEDS);assert.deepEqual(order.slice(0,6).map(x=>x.family),FAMILIES);
const played=new Set(FAMILIES.filter(f=>f!=='vidhide'));const v=[...schedule(many,played)];
assert.deepEqual(v.map(x=>x.episode),['streamwish0','vidhide0','mp4upload0','yourupload0','mega0','voe0','vidhide1','vidhide2','vidhide3']);assert.equal(embed({family:'voe',url:'http://x'}),null);
const day1=merge(null,[{family:'voe',state:'gone'},{family:'voe',state:'gone'},{family:'mega',state:'played'},{family:'vidhide',state:'no-video'},{family:'vidhide',state:'gone'},{family:'yourupload',state:'blocked-from-github'}],'2026-11-01','t1');
assert.equal(day1.families.voe.state,'failed');assert.equal(day1.families.voe.failingDays,1);assert.equal(day1.families.mega.state,'ok');
assert.equal(day1.families.vidhide.state,'unknown','no clear deletion on every attempt');assert.equal(day1.families.vidhide.failingDays,0);
assert.equal(day1.families.yourupload.state,'blocked');assert.equal(day1.families.mp4upload.state,'no-sample');
assert.equal(merge(day1,[{family:'voe',state:'gone'}],'2026-11-01','t1b').families.voe.failingDays,1,'same day does not count twice');
const day2=merge(day1,[{family:'voe',state:'gone'},{family:'mega',state:'not-advancing'}],'2026-11-02','t2');
assert.equal(day2.families.voe.failingDays,2);assert.equal(day2.families.mega.state,'unknown');assert.equal(day2.families.mega.failingDays,0);assert.equal(day2.families.mega.lastOkAt,'t1');
assert.equal(merge(day2,[{family:'voe',state:'played'}],'2026-11-03','t3').families.voe.failingDays,0);
assert.deepEqual(Object.keys(day1.families),FAMILIES);
// Serve a tiny generated VP8 clip so the test uses Chromium's native decoder.
const video=fs.readFileSync(new URL('./fixtures/playback-test.webm',import.meta.url));
const fake=http.createServer((req,res)=>{
 if(req.url==='/fixture.webm'){
  res.writeHead(200,{'content-type':'video/webm','content-length':video.length}).end(video);
  return;
 }
 const html={'content-type':'text/html'};
 if(req.url==='/e/blocked'){res.writeHead(403,html).end('<title>Just a moment...</title>cf-chl');return;}
 if(req.url==='/e/gone'){res.writeHead(404,html).end('<title>404 - Not found</title>');return;}
 if(req.url==='/e/adnotfound'){res.writeHead(200,html).end('<iframe srcdoc="<h1>404 - Not found</h1>"></iframe>');return;}
 if(req.url==='/e/deleted'){res.writeHead(200,html).end('<h1>File was deleted</h1>');return;}
 if(req.url==='/e/jw'){
  res.writeHead(200,html).end(`<!doctype html><button class="jw-icon-display">Play</button><video muted playsinline></video><script>
   document.querySelector('button').onclick=event=>{
    event.currentTarget.remove();
    const player=document.querySelector('video');
    player.src='/fixture.webm';
    player.play().catch(()=>{});
   };
  </script>`);
  return;
 }
 const body=req.url==='/e/live'?'<video src="/fixture.webm" autoplay muted playsinline></video>':'<video src="/none.webm"></video>';
 res.writeHead(200,html).end('<!doctype html>'+body);
}).listen(0,'127.0.0.1');
await new Promise(r=>fake.on('listening',r));
// Different ports keep the iframe cross-origin.
const base='http://127.0.0.1:'+fake.address().port,server=await serve(),origin='http://127.0.0.1:'+server.address().port;
let browser;
try{
 browser=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required']});
 const target=route=>({family:'test',episode:'e',url:base+route,embed:base+route});
 const live=await probeOne(browser,origin,target('/e/live'));
 assert.equal(live.state,'played',JSON.stringify(live));
 assert.ok(live.advanced>3);
 const dead=await probeOne(browser,origin,target('/e/dead'));
 assert.notEqual(dead.state,'played');
 const blocked=await probeOne(browser,origin,target('/e/blocked'));
 assert.equal(blocked.state,'blocked-from-github',JSON.stringify(blocked));
 assert.equal((await probeOne(browser,origin,target('/e/gone'))).state,'gone');
 assert.equal((await probeOne(browser,origin,target('/e/deleted'))).state,'gone');
 assert.notEqual((await probeOne(browser,origin,target('/e/adnotfound'))).state,'gone','An ad frame is not a deletion');
 const overlay=await probeOne(browser,origin,target('/e/jw'));
 assert.equal(overlay.state,'played','The overlay must start playback: '+JSON.stringify(overlay));
}finally{
 if(browser)await browser.close();
 server.close();
 fake.close();
}
console.log('playback probe controls PASS (selection, day logic, played/not-played/blocked in real Chromium)');
