// 9/11/2026: daily cap per account (REVISION.md C5). One Durable Object counts, per UTC day, what each account asks
// for. QUOTA_MODE "count" (default) only counts and lists accounts over QUOTA_DAY; "enforce" refuses them with 429.
// Counts live in memory and are saved every 10 requests (Workers Free write budget); a restart can lose a few.
// Any failure lets the request through: a counting problem must never leave the app without links.
export class Quota{
 constructor(state){this.sql=state.storage.sql;this.sql.exec('create table if not exists q(day text not null,user text not null,n integer not null,primary key(day,user))');this.mem=new Map();this.day='';}
 save(day,user,n){this.sql.exec('insert into q(day,user,n) values(?,?,?) on conflict(day,user) do update set n=max(n,excluded.n)',day,user,n);}
 async fetch(request){
  const u=new URL(request.url),day=new Date().toISOString().slice(0,10);
  if(day!==this.day){for(const [k,n] of this.mem){const [d,user]=k.split('|');this.save(d,user,n);}this.mem.clear();this.day=day;
   const old=new Date(Date.now()-14*86400000).toISOString().slice(0,10);this.sql.exec('delete from q where day<?',old);}
  if(u.pathname==='/hit'){
   const user=u.searchParams.get('u')||'',cap=Number(u.searchParams.get('cap'))||300,k=day+'|'+user;
   if(!/^[A-Za-z0-9-]{1,64}$/.test(user))return Response.json({n:0,over:false});
   let n=this.mem.get(k);if(n===undefined){const row=this.sql.exec('select n from q where day=? and user=?',day,user).toArray()[0];n=row?row.n:0;}
   n++;this.mem.set(k,n);if(n%10===0||n===cap+1)this.save(day,user,n);
   return Response.json({n,over:n>cap});
  }
  if(u.pathname==='/report'){
   const cap=Number(u.searchParams.get('cap'))||300;for(const [k,n] of this.mem){const [d,user]=k.split('|');this.save(d,user,n);}
   const rows=this.sql.exec('select day,user,n from q order by day desc,n desc limit 400').toArray();
   const days={};for(const r of rows){const d=days[r.day]||={accounts:0,over:[],top:0};d.accounts++;d.top=Math.max(d.top,r.n);if(r.n>cap&&d.over.length<30)d.over.push({user:r.user,n:r.n});}
   return Response.json({schema:1,cap,days});
  }
  return new Response('{}',{status:404});
 }
}
const quotaStub=env=>env.QUOTA.get(env.QUOTA.idFromName('global'));
/** true when the request may go on; false only when the account is over the cap AND QUOTA_MODE is "enforce". */
export async function quotaAllows(env,user){
 if(!env.QUOTA||!user)return true;
 try{const cap=Number(env.QUOTA_DAY)||300,r=await quotaStub(env).fetch('https://quota/hit?u='+encodeURIComponent(user)+'&cap='+cap);const x=await r.json();return !(x.over&&env.QUOTA_MODE==='enforce');}catch{return true;}
}
export async function quotaReport(env){const cap=Number(env.QUOTA_DAY)||300;return quotaStub(env).fetch('https://quota/report?cap='+cap);}
