'use strict';
// Only public JK documents/API; no providers, JS execution, images or video requests.
const MAX=4*1024*1024,fs=require('fs'),{rateBlocked,retryDelay}=require('./rate-rules.cjs');
class Http {
 constructor(gap=500,config={}){this.gap=gap;this.next=Promise.resolve();this.cookies=new Map();this.requests=0;this.bytes=0;this.lastStart=0;this.pauseUntil=0;this.config=config;this.now=config.now||Date.now;this.sleep=config.sleep||(ms=>new Promise(r=>setTimeout(r,ms)));this.fetch=config.fetch||fetch;if(config.cooldownFile){try{this.pauseUntil=JSON.parse(fs.readFileSync(config.cooldownFile)).notBefore||0;}catch{}}}
 async turn(){let release;const previous=this.next;this.next=new Promise(r=>release=r);await previous;try{for(;;){while(this.pauseUntil>this.now()){if(this.config.onThrottle)this.config.onThrottle(this.pauseUntil);await this.sleep(Math.min(60000,this.pauseUntil-this.now()));}if(this.pauseUntil){this.pauseUntil=0;if(this.config.onResume)this.config.onResume();}const wait=this.lastStart?this.lastStart+this.gap-this.now():0;if(wait>0){await this.sleep(wait);continue;}this.lastStart=this.now();break;}}finally{release();}}
 pause(response,text){const until=this.now()+retryDelay(response.headers.get('retry-after'),text,this.now());this.pauseUntil=Math.max(this.pauseUntil,until);if(this.config.cooldownFile){const file=this.config.cooldownFile;fs.writeFileSync(file+'.tmp',JSON.stringify({notBefore:this.pauseUntil,reason:'source-rate-limit',ipRotation:false}));fs.renameSync(file+'.tmp',file);}if(this.config.onThrottle)this.config.onThrottle(this.pauseUntil);}
 async get(url,options={}){const u=new URL(url);if(u.protocol!=='https:'||!['jkanime.net','www.jkanime.net'].includes(u.hostname)||u.username||u.password||u.port||(!/^\/[a-zA-Z0-9_-]+\/(?:[1-9][0-9]*\/)?$/.test(u.pathname)&&!/^\/ajax\/episodes\/[0-9]+\/[0-9]+$/.test(u.pathname)&&u.pathname!=='/'))throw Error('HTTP target not approved');
 let current=url,hops=0;
 for(let attempt=0;attempt<4;attempt++){
 await this.turn();this.requests++;const response=await this.fetch(current,{...options,redirect:'manual',signal:AbortSignal.timeout(20000),headers:{'User-Agent':'ZZAnimeCatalogBackup/1.0','Accept':options.method==='POST'?'application/json':'text/html','Cookie':[...this.cookies].map(([k,v])=>k+'='+v).join(';'),...(options.headers||{})}});
 for(const line of response.headers.getSetCookie()){const part=line.split(';',1)[0],i=part.indexOf('=');if(i>0)this.cookies.set(part.slice(0,i),part.slice(i+1));}
 const type=response.headers.get('content-type')||'';if(response.status===200&&!/text\/html|text\/plain|application\/json/i.test(type))throw Error('Unexpected document type');
 const parts=[];let size=0;for await(const chunk of response.body){size+=chunk.length;if(size>MAX)throw Error('Document limit exceeded');parts.push(chunk);}this.bytes+=size;const text=Buffer.concat(parts).toString('utf8');
 if(rateBlocked(response.status,text)){this.pause(response,text);if(attempt<3)continue;throw Object.assign(Error('Source rate limit persists; waiting before supervisor retry'),{stop:true,retryAt:this.pauseUntil});}
 if(response.status===302){const location=response.headers.get('location');let target;try{target=new URL(location,current)}catch{throw Error('Invalid redirect')};if(!this.config.allowObservedOna||hops++!==0||!u.pathname.endsWith('/1/')||!location||target.protocol!=='https:'||target.origin!==u.origin||target.username||target.password||target.port||target.search||target.hash||target.pathname!==u.pathname.replace(/1\/$/,'ona/'))throw Error('Unapproved redirect');if(this.config.onRedirect)this.config.onRedirect(url,target.href);current=target.href;continue;}
 if([403,503].includes(response.status))throw Object.assign(Error('Source refused HTTP '+response.status),{stop:true});if(response.status!==200)throw Error('HTTP '+response.status);return text;
 }
 }
}
module.exports={Http};
