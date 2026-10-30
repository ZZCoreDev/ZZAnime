// Cloudflare entry point; all rules live in logic.js so they run under the local tests too.
import {DurableObject} from 'cloudflare:workers';
import {handle,Store} from './logic.js';

export class HelpStore extends DurableObject{
 constructor(ctx,env){super(ctx,env);this.store=new Store(ctx.storage.sql);}
 take(limits,expires){return this.store.take(limits,expires);}
 add(rows){return this.store.add(rows);}
 candidates(since){return this.store.candidates(since);}
 check(key,since){return this.store.check(key,since);}
 saveCheck(key,verdict,now){return this.store.saveCheck(key,verdict,now);}
 cleanup(now){return this.store.cleanup(now);}
}

export default{
 async fetch(request,env){
  const store=env.STORE.get(env.STORE.idFromName('global'));
  try{return await handle(request,env,store);}
  catch{return new Response(JSON.stringify({error:'unavailable'}),{status:503,headers:{'content-type':'application/json'}});}
 }
};
