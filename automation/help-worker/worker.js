// Cloudflare entry point; all rules live in logic.js so they run under the local tests too.
import {DurableObject} from 'cloudflare:workers';
import {handle,Store} from './logic.js';

export class HelpStore extends DurableObject{
 constructor(ctx,env){super(ctx,env);this.store=new Store(ctx.storage.sql);}
 submit(items,limits,expires,now,sameAsnZones){return this.store.submit(items,limits,expires,now,sameAsnZones);}
 decide(results,now){return this.store.decide(results,now);}
 accepted(episodes,now){return this.store.accepted(episodes,now);}
 note(day,counts,expires){return this.store.note(day,counts,expires);}
 dead(items,limits,expires,now){return this.store.dead(items,limits,expires,now);}
 deadReports(now){return this.store.deadReports(now);}
 stats(now,sameAsnZones){return this.store.stats(now,sameAsnZones);}
 play(items,limits,expires,day){return this.store.play(items,limits,expires,day);}
 playStats(now){return this.store.playStats(now);}
}

export default{
 async fetch(request,env){
  const store=env.STORE.get(env.STORE.idFromName('global'));
  try{return await handle(request,env,store);}
  catch{return new Response(JSON.stringify({error:'unavailable'}),{status:503,headers:{'content-type':'application/json'}});}
 }
};
