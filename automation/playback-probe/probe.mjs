// Daily playback probe: opens each picked embed the way the app does (an unsandboxed iframe in a local
// page), presses play and checks that a <video> advances more than 3 s. No AI, no retries, pauses between
// embeds, at most 12 a day, never rotating IPs. Usage: node probe.mjs <published-assets> <previous.json> <out.json>
import fs from 'node:fs';import http from 'node:http';import {chromium} from 'playwright';
import {channelEpisodes,pick,merge,schedule} from './select.mjs';
const [assets,previousPath,outPath]=process.argv.slice(2);
const PAUSE=Number(process.env.PROBE_PAUSE_MS||20000),WAIT=Number(process.env.PROBE_WAIT_MS||60000),ADVANCE=3;
// A clear deletion: the embed answers 404/410 or its page says so. Anything else stays inconclusive.
const GONE=/File not found|File was deleted|no longer available|has been deleted|We can.t find the video|Video not found|404 - Not found|Content Invalid|File does not exist/i;
const PLAY=['.jw-icon-display','.jw-display-icon-container','.vjs-big-play-button','.plyr__control--overlaid','button[aria-label*="Play" i]','.play-button','#play'];
const BLOCK=/cf-chl|Just a moment|Attention Required|Access denied|you have been blocked|captcha/i;
export async function probeOne(browser,origin,target){
 const context=await browser.newContext({viewport:{width:1280,height:720}});const page=await context.newPage();
 context.on('page',p=>{if(p!==page)p.close().catch(()=>{});});            // ad pop-ups: closed, never followed
 let status=null,blocked=false;
 page.on('response',async r=>{if(r.url()===target.embed||r.request().frame()?.parentFrame()===page.mainFrame()&&r.request().isNavigationRequest()){status=status??r.status();if([403,429,503].includes(r.status())){try{blocked=blocked||BLOCK.test(await r.text())||r.status()===403}catch{blocked=true}}}});
 const result={episode:target.episode,observedAt:target.observedAt,name:target.name,url:target.url,embed:target.embed};
 try{
  await page.goto(origin+'/probe.html?src='+encodeURIComponent(target.embed),{waitUntil:'domcontentloaded',timeout:30000});
  const box=await (await page.$('iframe')).boundingBox();await page.waitForTimeout(8000);
  let start=null,best=0,gone=[404,410].includes(status);const deadline=Date.now()+WAIT;let clicks=0;
  while(Date.now()<deadline&&!gone){
   if(clicks<5&&best===0){
    // Players such as jwplayer only start from their own overlay; ad layers swallow the first clicks.
    let hit=false;
    for(const frame of page.frames().slice(1))for(const sel of PLAY){if(!hit&&await frame.click(sel,{timeout:500}).then(()=>true).catch(()=>false))hit=true;}
    if(!hit)await page.mouse.click(box.x+box.width/2,box.y+box.height/2).catch(()=>{});clicks++;
   }
   for(const frame of page.frames().slice(1)){if(await frame.evaluate(re=>new RegExp(re,'i').test((document.title||'')+' '+(document.body?.innerText||'').slice(0,4000)),GONE.source).catch(()=>false)){gone=true;}}
   for(const frame of page.frames()){
    const t=await frame.evaluate(()=>{const v=[...document.querySelectorAll('video')].sort((a,b)=>b.currentTime-a.currentTime)[0];if(!v)return null;if(v.paused&&v.readyState>=2){v.muted=true;v.play().catch(()=>{});}return v.currentTime;}).catch(()=>null);
    if(typeof t==='number'){if(start===null)start=t;best=Math.max(best,t-start);}
   }
   if(best>ADVANCE)break;await page.waitForTimeout(2000);
  }
  Object.assign(result,{status,advanced:Math.round(best*10)/10,state:best>ADVANCE?'played':blocked?'blocked-from-github':gone||[404,410].includes(status)?'gone':start===null?'no-video':'not-advancing'});
 }catch(error){Object.assign(result,{status,state:blocked?'blocked-from-github':'error',reason:String(error.message||error).slice(0,160)});}
 await context.close();return result;
}
export function serve(){
 return new Promise(resolve=>{const s=http.createServer((req,res)=>{const u=new URL(req.url,'http://x');
  if(u.pathname!=='/probe.html'){res.writeHead(404).end();return;}
  const src=String(u.searchParams.get('src')||'').replace(/"/g,'&quot;');
  res.writeHead(200,{'content-type':'text/html'}).end(`<!doctype html><html><body style="margin:0;background:#000"><iframe src="${src}" style="border:0;width:100vw;height:100vh" allow="autoplay; fullscreen; encrypted-media" allowfullscreen referrerpolicy="origin"></iframe></body></html>`);
 }).listen(0,'127.0.0.1',()=>resolve(s));});
}
async function main(){
 const episodes=[...channelEpisodes(assets),...channelEpisodes(assets,'voe/'),...channelEpisodes(assets,'extra/')];
 const targets=pick(episodes),server=await serve(),origin='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required']});const results=[];
 const played=new Set();let i=0;
 for(const t of schedule(targets,played)){if(i++)await new Promise(r=>setTimeout(r,PAUSE));const r=await probeOne(browser,origin,t);results.push({family:t.family,...r});if(r.state==='played')played.add(t.family);console.log(JSON.stringify({family:t.family,state:r.state,advanced:r.advanced,status:r.status}));}
 await browser.close();server.close();
 let previous=null;try{previous=JSON.parse(fs.readFileSync(previousPath))}catch{}
 const now=new Date().toISOString();const out=merge(previous,results,now.slice(0,10),now);
 fs.writeFileSync(outPath,JSON.stringify(out,null,1)+'\n');console.log(JSON.stringify(Object.fromEntries(Object.entries(out.families).map(([f,v])=>[f,v.state+'/'+v.failingDays]))));
}
if(import.meta.url==='file://'+process.argv[1])main().catch(e=>{console.error(e);process.exit(1);});
