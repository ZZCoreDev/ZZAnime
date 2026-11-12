// 169 (9/11/2026): door of zzanime-respaldo. The signed pointers (channel.json of each channel) stay public: the
// help worker and old apps read them. The files with the links (indexes/, series/) need, once REQUIRE_SESSION is
// "true", a ZZAnime session (checked with the project's public ES256 keys, no secret) or the cloud's own key
// (X-ZZ-Cloud, for the publication check in run.py). CHANNEL_LIMIT slows down bulk copying per account.
import {quotaAllows,quotaReport,banSelf,quotaTally,linkAllows,humanOk,QuotaUnavailable} from './quota.mjs';
export {Quota} from './quota.mjs';
const ISSUER='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',JWKS=ISSUER+'/.well-known/jwks.json';
const PUBLIC=/^\/(?:(?:voe|extra)\/)?channel\.json$/;
// 9/11: the editor's link-health view (owner_files.py), only for the editor owner with authenticator (zz_editor_access).
const OWNER=/^\/owner\/(?:help-status|cloud-runs|link-health(?:-[0-9]{1,2})?)\.json$/;
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
export async function handle(request,env,fetcher=(...a)=>globalThis.fetch(...a)){
 const path=new URL(request.url).pathname;
 // The daily-cap report also answers the cloud's own key (health_watch.py warns of new bans); never the other /owner/ files.
 if(path==='/owner/quota.json'){if(!same(request.headers.get('X-ZZ-Cloud')||'',env.CLOUD_KEY||'')&&!await owner(request,fetcher))return deny(403,'owner');try{const r=await quotaReport(env);return new Response(r.body,{status:r.status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'}});}catch{return deny(503,'quota');}}
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
  const main=path.startsWith('/series/');
  // voe/ and extra/ hold the same series' extra servers: they keep the request cap (quotaAllows) so one tap is not counted 3 times.
  if(env.LINK_RULES==='enforce'&&user&&main){const token=request.headers.get('X-ZZ-Human')||'';
   const out={},r=await linkAllows(env,{user,fresh,device,ban,item:path,out,human:token?await humanOk(env,token,ip,fetcher):''});
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
