// 169 (9/11/2026): door of zzanime-respaldo. The signed pointers (channel.json of each channel) stay public: the
// help worker and old apps read them. The files with the links (indexes/, series/) need, once REQUIRE_SESSION is
// "true", a ZZAnime session (checked with the project's public ES256 keys, no secret) or the cloud's own key
// (X-ZZ-Cloud, for the publication check in run.py). CHANNEL_LIMIT slows down bulk copying per account.
import {quotaAllows,quotaReport,banSelf,quotaTally,linkAllows,humanOk,QuotaUnavailable,hcaptchaVerify,hcaptchaMark,hcaptchaPassed,ownerCounter,netOf,resetOwnerConf} from './quota.mjs';
export {Quota} from './quota.mjs';
const ISSUER='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',JWKS=ISSUER+'/.well-known/jwks.json';
const PUBLIC=/^\/(?:(?:voe|extra)\/)?channel\.json$/;
// 9/11: the editor's link-health view (owner_files.py), only for the editor owner with authenticator (zz_editor_access).
const OWNER=/^\/owner\/(?:help-status|cloud-runs|semaforo|link-health(?:-[0-9]{1,2})?)\.json$/;
// Public project key of the app (also inside the APK): lets the owner check run as the caller.
const SUPABASE_KEY='sb_publishable_33FCU_W4f4gR3a69SygtDQ_j3sG1A-m';
let keys=null,keysAt=0,loading=null,kidRetryAt=0,refreshAfter=0,lastOk=false;
const b64url=s=>Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')+'==='.slice((s.length+3)%4)),c=>c.charCodeAt(0));
export function resetKeys(){keys=null;keysAt=0;loading=null;kidRetryAt=0;refreshAfter=0;lastOk=false;}
// 11/11 quinta revisión: a token signed with a key that is not in the cached set (Supabase rotated its keys) reloads
// the set once (shared by concurrent requests, at most every 30 s), and the set is only replaced once fully imported.
async function loadKeys(fetcher,now){
 if(!loading)loading=(async()=>{try{const r=await fetcher(JWKS,{signal:AbortSignal.timeout(8000)});if(r.status!==200)throw Error('JWKS');const set=await r.json();const next=new Map();for(const k of set.keys||[])if(k.kty==='EC'&&k.crv==='P-256'&&k.alg==='ES256'&&k.kid)next.set(k.kid,await crypto.subtle.importKey('jwk',{kty:'EC',crv:'P-256',x:k.x,y:k.y,ext:true},{name:'ECDSA',namedCurve:'P-256'},false,['verify']));keys=next;keysAt=now;}finally{loading=null;}})();
 return loading;
}
// 12/11 sexta revisión W6-01: every reload (expired cache or unknown kid) shares one 30 s pause, and a key set that
// cannot be read is «unavailable» (JwksUnavailable → 503 Retry-After), never «no session» (which forced a new login).
let tallyTick=0;const TALLY_EVERY=50;
// 12/11 décima revisión R10-01: which series each published file belongs to, read from our own signed channel and index
// (main, voe/ and extra/ each have their own). Cached per index version; a file that is not in the current index is 404.
const seriesMaps=new Map();
async function seriesOf(env,prefix,file){try{return await seriesOfIndex(env,prefix,file);}catch(e){if(e instanceof QuotaUnavailable)throw e;throw new QuotaUnavailable();}}
async function seriesOfIndex(env,prefix,file){
 const ch=await env.ASSETS.fetch(new Request('https://assets.local/'+prefix+'channel.json'));if(ch.status!==200)throw new QuotaUnavailable();
 const payload=JSON.parse((await ch.json()).payload),indexPath=String(payload.indexPath||'');if(!/^indexes\/[a-f0-9]{64}\.bin$/.test(indexPath))throw new QuotaUnavailable();
 let cached=seriesMaps.get(prefix);
 if(!cached||cached.index!==indexPath){const r=await env.ASSETS.fetch(new Request('https://assets.local/'+prefix+indexPath));if(r.status!==200)throw new QuotaUnavailable();
  const index=await r.json(),map=new Map();for(const [key,entry] of Object.entries(index?.series||{}))if(/^[a-f0-9]{64}$/.test(key)&&typeof entry?.path==='string')map.set(entry.path,key);
  cached={index:indexPath,map};seriesMaps.set(prefix,cached);}
 return cached.map.get(file)||'';
}
export function resetSeriesMaps(){seriesMaps.clear();}
export class JwksUnavailable extends Error{constructor(){super('JWKS unavailable');this.code='upstream_503';}}
async function refresh(fetcher,now){
 if(loading){try{await loading;lastOk=true;}catch{lastOk=false;}return lastOk?'ok':'down';}
 if(now<refreshAfter)return lastOk?'pause':'down';
 refreshAfter=now+30000;try{await loadKeys(fetcher,now);lastOk=true;}catch{lastOk=false;}return lastOk?'ok':'down';
}
async function publicKey(kid,fetcher,now){
 let fresh=false;
 if(!keys||now-keysAt>3600000){const r=await refresh(fetcher,now);if(r==='down'||!keys||now-keysAt>3600000)throw new JwksUnavailable();fresh=true;}
 if(!keys.has(kid)&&!fresh){const r=await refresh(fetcher,now);if(r==='down')throw new JwksUnavailable();}
 return keys.get(kid)||null;
}
export async function sessionUser(request,fetcher=(...a)=>globalThis.fetch(...a),now=Date.now()){return (await sessionInfo(request,fetcher,now)).sub;}
// 10/11: zz_new (claim added by the access-token hook, 031) marks accounts created in the last 7 days.
export async function sessionInfo(request,fetcher=(...a)=>globalThis.fetch(...a),now=Date.now()){const sub=await verifiedSub(request,fetcher,now);return {sub:sub?sub.sub:'',fresh:!!sub&&sub.fresh};}
async function verifiedSub(request,fetcher,now){
 const m=/^Bearer ([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)$/.exec(request.headers.get('Authorization')||'');if(!m)return '';
 try{
  const header=JSON.parse(new TextDecoder().decode(b64url(m[1]))),claims=JSON.parse(new TextDecoder().decode(b64url(m[2])));
  if(header.alg!=='ES256'||typeof header.kid!=='string')return '';
  const key=await publicKey(header.kid,fetcher,now);if(!key)return '';
  if(!await crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},key,b64url(m[3]),new TextEncoder().encode(m[1]+'.'+m[2])))return '';
  // 2 h grace: a phone back from sleep sends its last token before refreshing it.
  return claims.iss===ISSUER&&claims.role==='authenticated'&&claims.is_anonymous!==true&&typeof claims.sub==='string'&&claims.sub.length>0&&typeof claims.exp==='number'&&claims.exp*1000>now-60000&&(claims.nbf===undefined||typeof claims.nbf==='number'&&claims.nbf*1000<=now+60000)&&(claims.aud==='authenticated'||Array.isArray(claims.aud)&&claims.aud.includes('authenticated'))?/* 11/11 auditoría M-01: 1 min de tolerancia (la app 186+ renueva antes) */{sub:claims.sub,fresh:claims.zz_new===true}:'';
 }catch(e){if(e instanceof JwksUnavailable)throw e;return '';}
}
function same(a,b){if(!a||!b||a.length!==b.length)return false;let d=0;for(let i=0;i<a.length;i++)d|=a.charCodeAt(i)^b.charCodeAt(i);return d===0;}
const deny=(status,error)=>new Response(JSON.stringify({error}),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
async function owner(request,fetcher){
 const auth=request.headers.get('Authorization')||'';if(!/^Bearer [A-Za-z0-9._-]{20,4096}$/.test(auth))return false;
 try{const r=await fetcher(ISSUER.replace('/auth/v1','/rest/v1/rpc/zz_editor_access'),{method:'POST',headers:{apikey:SUPABASE_KEY,Authorization:auth,'Content-Type':'application/json'},body:'{}',redirect:'manual',signal:AbortSignal.timeout(10000)});
  if(r.status!==200)return false;const x=await r.json();return x?.allowed===true&&x?.aal2===true;}catch{return false;}
}
// 13/11 (Robin): hCaptcha of the "soy humano" page (zzanime.uk/humano). POST n=<challenge>&t=<hCaptcha token> marks the
// challenge once api.hcaptcha.com confirms it; GET ?n=<challenge> answers whether it was marked (the editor asks it). No
// session needed (the page has none); a solved hCaptcha only adds to a box that still has to be passed for that challenge.
const PAGE_ORIGIN='https://zzanime.uk';
async function humanRoute(request,env,fetcher){
 const cors={'Access-Control-Allow-Origin':PAGE_ORIGIN,'Vary':'Origin','Cache-Control':'no-store','Content-Type':'application/json'},answer=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:cors});
 if(request.method==='OPTIONS')return new Response(null,{status:204,headers:{...cors,'Access-Control-Allow-Methods':'POST','Access-Control-Allow-Headers':'Content-Type','Access-Control-Max-Age':'600'}});
 if(request.method!=='GET'&&request.method!=='POST')return answer({ok:false},405);
 // 13/11 repaso: GET and POST from the internet are limited per connection (Cloudflare always sets CF-Connecting-IP there), so
 // nobody can spend the counter's daily budget with anonymous requests; the editor's binding call carries no IP.
 const ip=request.headers.get('CF-Connecting-IP')||'';
 if(env.CHANNEL_LIMIT&&ip){const {success}=await env.CHANNEL_LIMIT.limit({key:'h:'+ip});if(!success)return answer({ok:false,error:'slow_down'},429);}
 if(request.method==='GET')return answer({ok:await hcaptchaPassed({QUOTA:env.QUOTA},new URL(request.url).searchParams.get('n')||'')});
 let form;try{const text=await request.text();if(text.length>10000)return answer({ok:false},413);form=new URLSearchParams(text);}catch{return answer({ok:false},400);}
 const nonce=form.get('n')||'',token=form.get('t')||'';if(!/^[a-f0-9]{32}$/.test(nonce))return answer({ok:false},400);
 if(!await hcaptchaVerify(env,token,ip,fetcher))return answer({ok:false});
 return answer({ok:await hcaptchaMark(env,nonce)});
}
/** The verified token (owner() asked Supabase) carries when its authenticator code was entered (amr). */
function recentTotp(request){try{const p=JSON.parse(new TextDecoder().decode(b64url((request.headers.get('Authorization')||'').split('.')[1]||'')));
 return Array.isArray(p.amr)&&p.amr.some(x=>x&&x.method==='totp'&&Number(x.timestamp)*1000>Date.now()-600000);}catch{return false;}}
/** Owner action → counter admin path (whitelisted, validated); null when not allowed. */
export function adminPath(a){if(!a||typeof a!=='object')return null;const user=String(a.user||''),hours=Math.min(Math.max(parseInt(a.hours,10)||24,1),720);
 if(a.action==='ban-user'&&/^[0-9a-f-]{36}$/.test(user))return '/admin/ban?k=u:'+user+'&hours=6';
 if(a.action==='unban-user'&&/^[0-9a-f-]{36}$/.test(user))return '/admin/unban?k=u:'+user;
 if(a.action==='ban-net'){const n=netOf(a.ip);return n?'/admin/ban?k=n:'+encodeURIComponent(n)+'&hours='+hours:null;}
 if(a.action==='unban-net'){const n=netOf(String(a.net||'').replace(/::$/,'::1'))||(/^[0-9.]{7,15}$/.test(String(a.net||''))?netOf(a.net):'');return n?'/admin/unban?k=n:'+encodeURIComponent(n):null;}
 if(a.action==='set'&&/^(?:cap|newcap|soft|burst|grant|ipcap|hcaptcha)$/.test(String(a.name||''))){const v=a.value===''||a.value==null?'':String(parseInt(a.value,10));if(v!==''&&!/^-?[0-9]{1,5}$/.test(v))return null;return '/admin/set?name='+a.name+'&value='+v;}
 return null;}
export async function handle(request,env,fetcher=(...a)=>globalThis.fetch(...a)){
 const path=new URL(request.url).pathname;
 if(path==='/humano/h')return humanRoute(request,env,fetcher);
 // The daily-cap report also answers the cloud's own key (health_watch.py warns of new bans); never the other /owner/ files.
 if(path==='/owner/quota.json'){if(!same(request.headers.get('X-ZZ-Cloud')||'',env.CLOUD_KEY||'')&&!await owner(request,fetcher))return deny(403,'owner');try{const r=await quotaReport(env);return new Response(r.body,{status:r.status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}});}catch{return deny(503,'quota');}}
 // 13/11 (Robin, grupo 2): owner controls from the editor. Owner with authenticator (zz_editor_access, checked by Supabase);
 // changing anything also needs the authenticator code of the last 10 minutes (amr of that same verified token).
 if(path==='/owner/admin'){if(!['GET','POST'].includes(request.method))return deny(405,'method');if(!await owner(request,fetcher))return deny(403,'owner');
  const answer=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:{'Content-Type':'application/json','Cache-Control':'private, no-store'}});
  try{if(request.method==='GET'){const r=await ownerCounter(env,'/admin/state');return answer(r.body,r.status);}
   if(!recentTotp(request))return deny(401,'reauth');
   const text=await request.text();if(text.length>2048)return deny(413,'too_large');let a;try{a=JSON.parse(text);}catch{return deny(400,'json');}
   const plan=adminPath(a);if(!plan)return deny(400,'action');const r=await ownerCounter(env,plan);if(a.action==='set')resetOwnerConf();
   return answer({...r.body,apply:r.status===200?plan:null},r.status);}catch{return deny(503,'quota');}}
 if(path.startsWith('/owner/')){if(!OWNER.test(path))return deny(404,'not_found');if(!await owner(request,fetcher))return deny(403,'owner');const r=await env.ASSETS.fetch(request);return new Response(r.body,{status:r.status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}});}
 // 10/11: how many apps still reach the channel by the old address (decides when to close it).
 // 12/11 octava revisión R8-01: this public, unauthenticated pointer only counts 1 request in TALLY_EVERY per instance, so
 // anonymous traffic cannot spend the counter that the series files need. The old/new figures are a rough estimate only
 // (novena revisión: deterministic sampling does not keep the exact ratio); do not close the old address on them alone.
 if(path==='/channel.json'&&!(request.headers.get('X-ZZ-Cloud'))&&++tallyTick%TALLY_EVERY===0){const h=new URL(request.url).hostname;if(h.endsWith('.workers.dev'))await quotaTally(env,'old');else if(h.endsWith('zzanime.uk'))await quotaTally(env,'new');}
 if(PUBLIC.test(path))return env.ASSETS.fetch(request);
 // 11/11 auditoría M-04: lo leído con la llave de la nube tampoco va a cachés compartidas.
 if(same(request.headers.get('X-ZZ-Cloud')||'',env.CLOUD_KEY||'')){const r=await env.ASSETS.fetch(request),h=new Headers(r.headers);h.set('Cache-Control','private, no-store');return new Response(r.body,{status:r.status,headers:h});}
 // 10/11 (app 177): the old workers.dev address only shows old apps the signed pointer (with the required update)
 // and serves the cloud's own check; links go only through zzanime.uk, where Cloudflare's rate limit applies.
 // 10/11 (179): the old address stays open: some networks block the brand-new zzanime.uk domain (app falls back here).
 let info;try{info=await sessionInfo(request,fetcher);}catch(e){if(e instanceof JwksUnavailable)return new Response(JSON.stringify({error:'unavailable',retry:true}),{status:503,headers:{'Content-Type':'application/json','Cache-Control':'private, no-store','Retry-After':'30'}});throw e;}
 const {sub:user,fresh}=info;
 if(!user&&env.REQUIRE_SESSION!=='false')return deny(401,'login'); // 11/11 A-03: cerrado salvo «false» explícito
 if(user&&env.CHANNEL_LIMIT){const {success}=await env.CHANNEL_LIMIT.limit({key:user});if(!success)return deny(429,'slow_down');}
 // 9/11: daily cap per account (and per IP without session) on the series files; abusive accounts are banned (quota.mjs, 028).
 if(/^\/(?:(?:voe|extra)\/)?series\//.test(path))try{
  const ip=request.headers.get('CF-Connecting-IP')||'',device=(request.headers.get('X-ZZ-Device')||'').toLowerCase(),ban=user?()=>banSelf(ISSUER.replace('/auth/v1',''),SUPABASE_KEY,request.headers.get('Authorization'),fetcher):null;
  // 10/11 (app 180): LINK_RULES "enforce" counts distinct series/films opened (reopening is free), asks "soy humano" (428)
  // from 50 a day or 5 in 10 minutes, caps at 150 (60 new accounts), bans at 300 attempts. Episode lists (/lista/) stay free.
  // Off until 180 is the required version: old apps download these files when opening a ficha.
  const main=path.startsWith('/series/'),prefix=(/^\/((?:voe|extra)\/)/.exec(path)||[])[1]||'';
  // voe/ and extra/ hold the same series' extra servers: they keep the request cap (quotaAllows) so one tap is not counted 3 times.
  if(env.LINK_RULES==='enforce'&&user){const series=await seriesOf(env,prefix,path.slice(1+prefix.length));
   if(!series)return deny(404,'not_found'); // not in the current publication: never served uncounted
   const linkItem='s:'+series,token=request.headers.get('X-ZZ-Human')||'';
   const out={},r=await linkAllows(env,{user,fresh,device,ban,item:linkItem,out,ip,human:token?await humanOk(env,token,ip,fetcher):''});
   // 12/11 sexta revisión W6-02: the editor's web corrections read series through its relay and cannot show the box;
   // the editor owner with authenticator (aal2, checked with Supabase only at this point) is not asked.
   if(r==='human'&&!await owner(request,fetcher))return new Response(JSON.stringify({error:'human',...(out.challenge?{challenge:out.challenge}:{})}),{status:428,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});if(r==='limit')return deny(429,'daily_limit');}
  else{if(!await quotaAllows(env,{user,fresh,ip,device,ban}))return deny(429,'daily_limit');
   if(env.LINK_RULES==='count'&&user&&main)await linkAllows(env,{user,fresh,device,item:path});}
 }catch(e){if(e instanceof QuotaUnavailable)return new Response(JSON.stringify({error:'unavailable',retry:true}),{status:503,headers:{'Content-Type':'application/json','Cache-Control':'private, no-store','Retry-After':'120'}});throw e;}
 // 11/11 auditoría M-04: lo que necesita sesión nunca va a cachés compartidas.
 {const r=await env.ASSETS.fetch(request),h=new Headers(r.headers);h.set('Cache-Control','private, no-store');return new Response(r.body,{status:r.status,headers:h});}
}
export default {fetch:(request,env)=>handle(request,env)};
