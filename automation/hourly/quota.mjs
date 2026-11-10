// 9/11/2026: daily cap per account and per IP (REVISION.md C5). One Durable Object counts, per UTC day, what each
// account (u:<id>) or anonymous IP (ip:<address>) asks for. QUOTA_MODE "count" only counts; "enforce" refuses:
//  · an account over QUOTA_DAY (300) is refused for the rest of the day;
//  · an account that keeps asking past QUOTA_BAN (600) is BLOCKED: the Worker asks Supabase (zz_quota_ban, 028) to ban
//    that account and close its sessions, and refuses it here for 6 h (its last session cannot outlive that);
//    if Supabase answers that the account is the owner or exempt, it is let through instead;
//  · an anonymous IP over QUOTA_IP_DAY (3000) is refused for the rest of the day (IPs are shared: never banned).
//  · app 170+ sends X-ZZ-Device (a hash of the Android id): when an account is banned its device is banned for a year,
//    so a new account on the same phone or TV gets nothing either.
// Counts live in memory and are saved every 10 requests (Workers Free write budget); a restart can lose a few.
// Any failure lets the request through: a counting problem must never leave the app without links.
const KEY=/^(?:u:[A-Za-z0-9-]{1,64}|ip:[0-9A-Fa-f:.]{2,45}|d:[a-f0-9]{32})$/,DEVICE=/^[a-f0-9]{32}$/;
export class Quota{
 constructor(state){this.sql=state.storage.sql;
  this.sql.exec('create table if not exists q(day text not null,user text not null,n integer not null,primary key(day,user))');
  this.sql.exec('create table if not exists marks(key text primary key,kind text not null,until integer not null,at integer not null)');
  this.mem=new Map();this.day='';}
 save(day,key,n){this.sql.exec('insert into q(day,user,n) values(?,?,?) on conflict(day,user) do update set n=max(n,excluded.n)',day,key,n);}
 flush(){for(const [k,n] of this.mem){const i=k.indexOf('|');this.save(k.slice(0,i),k.slice(i+1),n);}}
 async fetch(request){
  const u=new URL(request.url),day=new Date().toISOString().slice(0,10),now=Date.now();
  if(day!==this.day){this.flush();this.mem.clear();this.day=day;
   this.sql.exec('delete from q where day<?',new Date(now-14*86400000).toISOString().slice(0,10));this.sql.exec('delete from marks where until<?',now);}
  const key=u.searchParams.get('k')||'';
  if(u.pathname==='/hit'){
   if(!KEY.test(key))return Response.json({n:0});
   const device=u.searchParams.get('d')||'';
   if(DEVICE.test(device)&&this.sql.exec("select 1 from marks where key=? and kind='ban' and until>?",'d:'+device,now).toArray().length)return Response.json({n:0,banned:true});
   const mark=this.sql.exec('select kind from marks where key=? and until>?',key,now).toArray()[0];
   if(mark)return Response.json({n:0,[mark.kind==='ban'?'banned':'exempt']:true});
   const cap=Number(u.searchParams.get('cap'))||300,ban=Number(u.searchParams.get('ban'))||0,k=day+'|'+key;
   let n=this.mem.get(k);if(n===undefined){const row=this.sql.exec('select n from q where day=? and user=?',day,key).toArray()[0];n=row?row.n:0;}
   n++;this.mem.set(k,n);if(n%10===0||n===cap+1||n===ban+1)this.save(day,key,n);
   return Response.json({n,over:n>cap,ban:ban>0&&n>ban});
  }
  if(u.pathname==='/mark'){
   const kind=u.searchParams.get('kind');if(!KEY.test(key)||!['ban','exempt'].includes(kind))return new Response('{}',{status:400});
   const until=now+(key.startsWith('d:')?365*86400000:kind==='ban'?6*3600000:30*86400000);
   this.sql.exec('insert into marks(key,kind,until,at) values(?,?,?,?) on conflict(key) do update set kind=excluded.kind,until=excluded.until,at=excluded.at',key,kind,until,now);
   return Response.json({ok:true});
  }
  if(u.pathname==='/report'){
   const cap=Number(u.searchParams.get('cap'))||300,ipCap=Number(u.searchParams.get('ipcap'))||3000;this.flush();
   const rows=this.sql.exec('select day,user,n from q order by day desc,n desc limit 600').toArray();
   const days={};for(const r of rows){const ip=r.user.startsWith('ip:'),d=days[r.day]||={accounts:0,ips:0,over:[],top:0,topIp:0};
    if(ip){d.ips++;d.topIp=Math.max(d.topIp,r.n);if(r.n>ipCap&&d.over.length<40)d.over.push({user:r.user,n:r.n});}
    else{d.accounts++;d.top=Math.max(d.top,r.n);if(r.n>cap&&d.over.length<40)d.over.push({user:r.user.replace(/^u:/,''),n:r.n});}}
   const bans=this.sql.exec("select key,until,at from marks where kind='ban' and key like 'u:%' and until>? order by at desc limit 50",now).toArray().map(b=>({user:b.key.replace(/^u:/,''),at:new Date(b.at).toISOString()}));
   const deviceBans=this.sql.exec("select at from marks where kind='ban' and key like 'd:%' and until>? order by at desc",now).toArray().map(b=>({at:new Date(b.at).toISOString()}));
   return Response.json({schema:1,cap,ipCap,days,bans,bannedDevices:deviceBans.length,deviceBans:deviceBans.slice(0,50)});
  }
  return new Response('{}',{status:404});
 }
}
const quotaStub=env=>env.QUOTA.get(env.QUOTA.idFromName('global'));
/** Bans the caller's own account in Supabase (028): {banned:true}, {banned:false} for the owner/exempt, or null. */
export async function banSelf(supabase,key,authorization,fetcher){
 try{const r=await fetcher(supabase+'/rest/v1/rpc/zz_quota_ban',{method:'POST',headers:{apikey:key,Authorization:authorization,'Content-Type':'application/json'},body:JSON.stringify({p_reason:'tope diario superado'}),redirect:'manual',signal:AbortSignal.timeout(10000)});
  return r.status===200?await r.json():null;}catch{return null;}
}
/** true when the request may go on. user: verified account id or ''; ip: CF-Connecting-IP; ban(): banSelf for that account. */
// 10/11 (REVISION-2 N3): banned accounts/devices are remembered here for 10 minutes, so one that keeps hammering does
// not spend the counter's free daily budget (when the counter fails, everything is let through).
const remembered=new Map();
const REMEMBER=600000;
export function forgetBans(){remembered.clear();}
function recall(k,now){const until=remembered.get(k);if(until&&until>now)return true;if(until)remembered.delete(k);return false;}
function remember(k,now){if(remembered.size>5000)remembered.clear();remembered.set(k,now+REMEMBER);}
/** fresh: account created in the last 7 days (claim zz_new, 031): smaller daily cap QUOTA_NEW_DAY (60) (REVISION-2 N2). */
export async function quotaAllows(env,{user='',ip='',ban=null,device='',fresh=false}={}){
 if(!env.QUOTA)return true;
 const key=user?'u:'+user:ip?'ip:'+ip:'',dev=DEVICE.test(device)?device:'';if(!KEY.test(key))return true;
 const enforce=env.QUOTA_MODE==='enforce',now=Date.now();
 if(enforce&&(recall(key,now)||dev&&recall('d:'+dev,now)))return false;
 try{
  const stub=quotaStub(env),normal=user?Number(env.QUOTA_DAY)||300:Number(env.QUOTA_IP_DAY)||3000,cap=user&&fresh?Number(env.QUOTA_NEW_DAY)||60:normal,banAt=user?Number(env.QUOTA_BAN)||2*normal:0;
  const x=await (await stub.fetch('https://quota/hit?k='+encodeURIComponent(key)+'&cap='+cap+'&ban='+banAt+(dev?'&d='+dev:''))).json();
  if(x.exempt)return true;
  if(x.banned){if(enforce)remember(key,now);return !enforce;}
  if(x.ban&&enforce&&ban){const r=await ban();
   await stub.fetch('https://quota/mark?k='+encodeURIComponent(key)+'&kind='+(r&&r.banned===false?'exempt':'ban'));
   if(dev&&r?.banned!==false){await stub.fetch('https://quota/mark?k=d:'+dev+'&kind=ban');remember('d:'+dev,now);}
   if(r?.banned!==false)remember(key,now);
   return r?.banned===false;}
  return !(x.over&&enforce);
 }catch{return true;}
}
export async function quotaReport(env){return quotaStub(env).fetch('https://quota/report?cap='+(Number(env.QUOTA_DAY)||300)+'&ipcap='+(Number(env.QUOTA_IP_DAY)||3000));}
