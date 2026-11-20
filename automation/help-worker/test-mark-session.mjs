const issuer='https://zavtyglqhcfriqnnukqw.supabase.co/auth/v1';
const keyPair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']);
const publicKey=await crypto.subtle.exportKey('jwk',keyPair.publicKey);
const encode=value=>Buffer.from(JSON.stringify(value)).toString('base64url');

export async function markAuthorization(account,now){
 const header=encode({alg:'ES256',kid:'mark-test'});
 const claims=encode({iss:issuer,role:'authenticated',aud:'authenticated',sub:account,exp:Math.floor(now/1000)+600});
 const payload=header+'.'+claims;
 const signature=await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},keyPair.privateKey,Buffer.from(payload));
 return 'Bearer '+payload+'.'+Buffer.from(signature).toString('base64url');
}

export function markFetcher(fallback){
 return (url,init)=>url===issuer+'/.well-known/jwks.json'
  ?Response.json({keys:[{...publicKey,alg:'ES256',kid:'mark-test'}]})
  :fallback(url,init);
}
