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
const MAX_FRAMES=16;
export async function probeOne(browser,origin,target){
 const context=await browser.newContext({viewport:{width:1280,height:720}});const page=await context.newPage();
 context.on('page',p=>{if(p!==page)p.close().catch(()=>{});});            // ad pop-ups: closed, never followed
 let status=null,blocked=false;
 page.on('response',r=>{
  try{
   const request=r.request();
   if(!request.isNavigationRequest()||r.url()!==target.embed&&request.frame()?.parentFrame()!==page.mainFrame())return;
   const code=r.status();
   if(code>=300&&code<400)return;
   status=code;
   if(code===403||code===429||r.headers()['cf-mitigated']==='challenge')blocked=true;
  }catch{} // A response may precede creation of its frame or belong to a worker.
 });
 const result={episode:target.episode,observedAt:target.observedAt,name:target.name,url:target.url,embed:target.embed};
 const inspect=async()=>{
  await page.goto(origin+'/probe.html?src='+encodeURIComponent(target.embed),{waitUntil:'domcontentloaded',timeout:30000});
  const box=await page.locator('iframe').boundingBox({timeout:5000});await page.waitForTimeout(8000);
  let start=null,best=0,gone=[404,410].includes(status);const deadline=Date.now()+WAIT;let clicks=0;
  while(Date.now()<deadline&&!gone&&!blocked){
   const frames=page.frames().slice(1,1+MAX_FRAMES);
   if(clicks<5&&best===0){
    // Players such as jwplayer only start from their own overlay; ad layers swallow the first clicks.
    let hit=false;
    for(const frame of frames)for(const sel of PLAY){if(!hit&&Date.now()<deadline&&await frame.click(sel,{timeout:500}).then(()=>true).catch(()=>false))hit=true;}
    if(!hit&&box)await page.mouse.click(box.x+box.width/2,box.y+box.height/2).catch(()=>{});clicks++;
   }
   // Only the embed's own frame: nested ad frames often say «Not found» and must not mark a file deleted.
   for(const frame of frames.filter(f=>f.parentFrame()===page.mainFrame())){
    const evidence=await frame.evaluate(({gonePattern,blockPattern})=>{
     let text=document.title.slice(0,512);
     if(document.body){
      const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
      for(let i=0;i<64&&text.length<4096;i++){
       const node=walker.nextNode();
       if(!node)break;
       const parent=node.parentElement;
       if(!parent||['SCRIPT','STYLE','NOSCRIPT'].includes(parent.tagName)||parent.checkVisibility?.({checkVisibilityCSS:true})===false)continue;
       text+=' '+node.substringData(0,Math.max(0,4095-text.length));
      }
     }
     return {gone:new RegExp(gonePattern,'i').test(text),blocked:new RegExp(blockPattern,'i').test(text)};
    },{gonePattern:GONE.source,blockPattern:BLOCK.source}).catch(()=>null);
    gone=gone||evidence?.gone===true;
    blocked=blocked||status===503&&evidence?.blocked===true;
   }
   for(const frame of frames){
    const t=await frame.evaluate(()=>{
     const videos=document.getElementsByTagName('video');
     let selected=null;
     for(let i=0;i<16;i++){
      const video=videos.item(i);
      if(!video)break;
      if(!selected||video.currentTime>selected.currentTime)selected=video;
     }
     if(!selected)return null;
     if(selected.paused&&selected.readyState>=2){selected.muted=true;selected.play().catch(()=>{});}
     return selected.currentTime;
    }).catch(()=>null);
    if(typeof t==='number'){if(start===null)start=t;best=Math.max(best,t-start);}
   }
   if(best>ADVANCE)break;await page.waitForTimeout(2000);
  }
  return {status,advanced:Math.round(best*10)/10,state:best>ADVANCE?'played':blocked?'blocked-from-github':gone||[404,410].includes(status)?'gone':start===null?'no-video':'not-advancing'};
 };
 let timer;
 try{
  const timeout=new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Playback probe timed out')),WAIT+45000);});
  Object.assign(result,await Promise.race([inspect(),timeout]));
 }catch(error){
  Object.assign(result,{status,state:blocked?'blocked-from-github':'error',reason:String(error.message||error).slice(0,160)});
 }finally{
  clearTimeout(timer);
  await context.close();
 }
 return result;
}
export function serve(){
 return new Promise(resolve=>{const s=http.createServer((req,res)=>{const u=new URL(req.url,'http://x');
  if(u.pathname!=='/probe.html'){res.writeHead(404).end();return;}
  const src=String(u.searchParams.get('src')||'').replace(/"/g,'&quot;');
  res.writeHead(200,{'content-type':'text/html'}).end(`<!doctype html><html><body style="margin:0;background:#000"><iframe src="${src}" style="border:0;width:100vw;height:100vh" allow="autoplay; fullscreen; encrypted-media" allowfullscreen referrerpolicy="origin"></iframe></body></html>`);
 }).listen(0,'127.0.0.1',()=>resolve(s));});
}
async function main(){
 // At most one probing pass per UTC day (12 embeds), unless started by hand.
 let earlier=null;try{earlier=JSON.parse(fs.readFileSync(previousPath))}catch{}
 if(process.env.PROBE_FORCE!=='1'&&String(earlier?.checkedAt||'').slice(0,10)===new Date().toISOString().slice(0,10)){console.log(JSON.stringify({skipped:'already-probed-today',checkedAt:earlier.checkedAt}));return;}
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
