// 169 (9/11/2026): door of zzanime-respaldo. The signed pointers (channel.json of each channel) stay public: the
// help worker and old apps read them. The files with the links (indexes/, series/) need, once REQUIRE_SESSION is
// "true", a ZZAnime session (checked with the project's public ES256 keys, no secret) or the cloud's own key
// (X-ZZ-Cloud, for the publication check in run.py). CHANNEL_LIMIT slows down bulk copying per account.
import {quotaAllows,quotaReport,banSelf} from './quota.mjs';
export {Quota} from './quota.mjs';
const ISSUER='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',JWKS=ISSUER+'/.well-known/jwks.json';
const PUBLIC=/^\/(?:(?:voe|extra)\/)?channel\.json$/;
// 9/11: the editor's link-health view (owner_files.py), only for the editor owner with authenticator (zz_editor_access).
const OWNER=/^\/owner\/(?:help-status|cloud-runs|link-health(?:-[0-9]{1,2})?)\.json$/;
// Public project key of the app (also inside the APK): lets the owner check run as the caller.
const SUPABASE_KEY='sb_publishable_33FCU_W4f4gR3a69SygtDQ_j3sG1A-m';
let keys=null,keysAt=0;
const b64url=s=>Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')+'==='.slice((s.length+3)%4)),c=>c.charCodeAt(0));
export function resetKeys(){keys=null;keysAt=0;}
async function publicKey(kid,fetcher,now){
 if(!keys||now-keysAt>3600000){const r=await fetcher(JWKS);if(r.status!==200)throw Error('JWKS');const set=await r.json();keys=new Map();for(const k of set.keys||[])if(k.kty==='EC'&&k.crv==='P-256'&&k.alg==='ES256'&&k.kid)keys.set(k.kid,await crypto.subtle.importKey('jwk',{kty:'EC',crv:'P-256',x:k.x,y:k.y,ext:true},{name:'ECDSA',namedCurve:'P-256'},false,['verify']));keysAt=now;}
 return keys.get(kid)||null;
}
export async function sessionUser(request,fetcher=(...a)=>globalThis.fetch(...a),now=Date.now()){
 const m=/^Bearer ([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)$/.exec(request.headers.get('Authorization')||'');if(!m)return '';
 try{
  const header=JSON.parse(new TextDecoder().decode(b64url(m[1]))),claims=JSON.parse(new TextDecoder().decode(b64url(m[2])));
  if(header.alg!=='ES256'||typeof header.kid!=='string')return '';
  const key=await publicKey(header.kid,fetcher,now);if(!key)return '';
  if(!await crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},key,b64url(m[3]),new TextEncoder().encode(m[1]+'.'+m[2])))return '';
  // 2 h grace: a phone back from sleep sends its last token before refreshing it.
  return claims.iss===ISSUER&&claims.role==='authenticated'&&claims.is_anonymous!==true&&typeof claims.sub==='string'&&claims.exp*1000>now-2*3600000?claims.sub:'';
 }catch{return '';}
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
 if(PUBLIC.test(path)||same(request.headers.get('X-ZZ-Cloud')||'',env.CLOUD_KEY||''))return env.ASSETS.fetch(request);
 const user=await sessionUser(request,fetcher);
 if(!user&&env.REQUIRE_SESSION==='true')return deny(401,'login');
 if(user&&env.CHANNEL_LIMIT){const {success}=await env.CHANNEL_LIMIT.limit({key:user});if(!success)return deny(429,'slow_down');}
 // 9/11: daily cap per account (and per IP without session) on the series files; abusive accounts are banned (quota.mjs, 028).
 if(/^\/(?:(?:voe|extra)\/)?series\//.test(path)&&!await quotaAllows(env,{user,ip:request.headers.get('CF-Connecting-IP')||'',device:(request.headers.get('X-ZZ-Device')||'').toLowerCase(),ban:user?()=>banSelf(ISSUER.replace('/auth/v1',''),SUPABASE_KEY,request.headers.get('Authorization'),fetcher):null}))return deny(429,'daily_limit');
 return env.ASSETS.fetch(request);
}
export default {fetch:(request,env)=>handle(request,env)};
