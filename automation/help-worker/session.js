// 10/11/2026 (REVISION-2 N5): help reports from app 176+ carry the ZZAnime session. It is checked with the project's
// public ES256 keys (no secret). REQUIRE_SESSION "true" (only once 176 is the minimum version) refuses reports without
// one; until then a session only adds a per-account daily limit.
const ISSUER='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',JWKS=ISSUER+'/.well-known/jwks.json';
let keys=null,keysAt=0,loading=null,kidRetryAt=0,refreshAfter=0,lastOk=false;
const b64url=s=>Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')+'==='.slice((s.length+3)%4)),c=>c.charCodeAt(0));
export function resetSessionKeys(){keys=null;keysAt=0;loading=null;kidRetryAt=0;refreshAfter=0;lastOk=false;}
// 11/11 quinta revisión: a token signed with a key that is not in the cached set (Supabase rotated its keys) reloads
// the set once (shared by concurrent requests, at most every 30 s), and the set is only replaced once fully imported.
async function loadKeys(fetcher,now){
 if(!loading)loading=(async()=>{try{const r=await fetcher(JWKS,{signal:AbortSignal.timeout(8000)});if(r.status!==200)throw Error('JWKS');const set=await r.json();const next=new Map();for(const k of set.keys||[])if(k.kty==='EC'&&k.crv==='P-256'&&k.alg==='ES256'&&k.kid)next.set(k.kid,await crypto.subtle.importKey('jwk',{kty:'EC',crv:'P-256',x:k.x,y:k.y,ext:true},{name:'ECDSA',namedCurve:'P-256'},false,['verify']));keys=next;keysAt=now;}finally{loading=null;}})();
 return loading;
}
// 12/11 sexta revisión W6-01: every reload (expired cache or unknown kid) shares one 30 s pause, and a key set that
// cannot be read is «unavailable» (JwksUnavailable → 503 Retry-After), never «no session» (which forced a new login).
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
/** The account id of a valid ZZAnime session, or ''. */
export async function sessionUser(request,fetcher,now=Date.now()){
 const m=/^Bearer ([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)$/.exec(request.headers.get('Authorization')||'');if(!m)return '';
 try{
  const header=JSON.parse(new TextDecoder().decode(b64url(m[1]))),claims=JSON.parse(new TextDecoder().decode(b64url(m[2])));
  if(header.alg!=='ES256'||typeof header.kid!=='string')return '';
  const key=await publicKey(header.kid,fetcher,now);if(!key)return '';
  if(!await crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},key,b64url(m[3]),new TextEncoder().encode(m[1]+'.'+m[2])))return '';
  return claims.iss===ISSUER&&claims.role==='authenticated'&&claims.is_anonymous!==true&&typeof claims.sub==='string'&&claims.sub.length>0&&typeof claims.exp==='number'&&claims.exp*1000>now-60000&&(claims.nbf===undefined||typeof claims.nbf==='number'&&claims.nbf*1000<=now+60000)&&(claims.aud==='authenticated'||Array.isArray(claims.aud)&&claims.aud.includes('authenticated'))?/* 11/11 auditoría M-01 */claims.sub:'';
 }catch(e){if(e instanceof JwksUnavailable)throw e;return '';}
}
