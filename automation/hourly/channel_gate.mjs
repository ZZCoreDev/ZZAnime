// 169 (9/11/2026): door of zzanime-respaldo. The signed pointers (channel.json of each channel) stay public: the
// help worker and old apps read them. The files with the links (indexes/, series/) need, once REQUIRE_SESSION is
// "true", a ZZAnime session (checked with the project's public ES256 keys, no secret) or the cloud's own key
// (X-ZZ-Cloud, for the publication check in run.py). CHANNEL_LIMIT slows down bulk copying per account.
const ISSUER='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',JWKS=ISSUER+'/.well-known/jwks.json';
const PUBLIC=/^\/(?:(?:voe|extra)\/)?channel\.json$/;
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
  return claims.iss===ISSUER&&claims.role==='authenticated'&&typeof claims.sub==='string'&&claims.exp*1000>now-2*3600000?claims.sub:'';
 }catch{return '';}
}
function same(a,b){if(!a||!b||a.length!==b.length)return false;let d=0;for(let i=0;i<a.length;i++)d|=a.charCodeAt(i)^b.charCodeAt(i);return d===0;}
const deny=(status,error)=>new Response(JSON.stringify({error}),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
export async function handle(request,env,fetcher=(...a)=>globalThis.fetch(...a)){
 const path=new URL(request.url).pathname;
 if(PUBLIC.test(path)||same(request.headers.get('X-ZZ-Cloud')||'',env.CLOUD_KEY||''))return env.ASSETS.fetch(request);
 const user=await sessionUser(request,fetcher);
 if(!user&&env.REQUIRE_SESSION==='true')return deny(401,'login');
 if(user&&env.CHANNEL_LIMIT){const {success}=await env.CHANNEL_LIMIT.limit({key:user});if(!success)return deny(429,'slow_down');}
 return env.ASSETS.fetch(request);
}
export default {fetch:(request,env)=>handle(request,env)};
