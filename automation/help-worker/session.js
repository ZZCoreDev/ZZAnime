// 10/11/2026 (REVISION-2 N5): help reports from app 176+ carry the ZZAnime session. It is checked with the project's
// public ES256 keys (no secret). REQUIRE_SESSION "true" (only once 176 is the minimum version) refuses reports without
// one; until then a session only adds a per-account daily limit.
const ISSUER='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1',JWKS=ISSUER+'/.well-known/jwks.json';
let keys=null,keysAt=0;
const b64url=s=>Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')+'==='.slice((s.length+3)%4)),c=>c.charCodeAt(0));
export function resetSessionKeys(){keys=null;keysAt=0;}
async function publicKey(kid,fetcher,now){
 if(!keys||now-keysAt>3600000){const r=await fetcher(JWKS);if(r.status!==200)throw Error('JWKS');const set=await r.json();keys=new Map();for(const k of set.keys||[])if(k.kty==='EC'&&k.crv==='P-256'&&k.alg==='ES256'&&k.kid)keys.set(k.kid,await crypto.subtle.importKey('jwk',{kty:'EC',crv:'P-256',x:k.x,y:k.y,ext:true},{name:'ECDSA',namedCurve:'P-256'},false,['verify']));keysAt=now;}
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
  return claims.iss===ISSUER&&claims.role==='authenticated'&&claims.is_anonymous!==true&&typeof claims.sub==='string'&&claims.exp*1000>now-2*3600000?claims.sub:'';
 }catch{return '';}
}
