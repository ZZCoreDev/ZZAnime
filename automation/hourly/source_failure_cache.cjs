'use strict';
// Best-effort warm-worker memory only. Never caches successful documents or dates.
class FailureCache {
 constructor(limit=1024,now=Date.now){this.rows=new Map();this.limit=limit;this.now=now;}
 keys(url){const u=new URL(url);return [u.origin,u.href];}
 get(url){for(const key of this.keys(url)){const row=this.rows.get(key);if(!row)continue;if(row.until<=this.now()){this.rows.delete(key);continue;}return row;}return null;}
 remember(url,status,retryAfter){
  const u=new URL(url);let key,delay;
  if(status===403&&u.hostname==='jkanime.net'){key=u.origin;delay=60000;}
  else if(status===404&&['tioanime.com','vww.animeflv.one'].includes(u.hostname)&&/^\/anime\/[-a-zA-Z0-9_]+$/.test(u.pathname)){key=u.href;delay=300000;}
  else return;
  if(retryAfter){const seconds=Number(retryAfter),until=Number.isFinite(seconds)?this.now()+Math.max(0,seconds)*1000:Date.parse(retryAfter);if(Number.isFinite(until))delay=Math.max(delay,until-this.now());}
  for(const [k,row] of this.rows)if(row.until<=this.now())this.rows.delete(k);
  if(!this.rows.has(key)&&this.rows.size>=this.limit)this.rows.delete(this.rows.keys().next().value);
  this.rows.set(key,{status,until:this.now()+delay});
 }
}
module.exports={FailureCache};
