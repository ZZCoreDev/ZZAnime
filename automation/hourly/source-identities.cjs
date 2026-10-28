'use strict';
const entries=require('./source-identities.json'),p=require('./lib/fast-rules.cjs');
function resolve(row,source,proof=false){
 const item=entries[row.url],fallback={slug:new URL(row.url).pathname.replaceAll('/',''),title:row.title,alias:false};
 if(!item||(!item.approved&&!proof))return fallback;
 if(row.year!==item.year||p.normal(row.title)!==p.normal(item.title))throw Error('Unverified source title/year');
 const mapped=item.sources[source];if(!mapped||!/^[-a-zA-Z0-9_]+$/.test(mapped.slug))throw Error('Unverified source mapping');return {...mapped,alias:true};
}
function canonicalSlug(slug,known,proof=false){
 if(known.has('https://jkanime.net/'+slug+'/'))return slug;
 const matches=Object.entries(entries).filter(([url,item])=>(item.approved||proof)&&Object.values(item.sources).some(s=>s.slug===slug)&&known.has(url));
 if(matches.length!==1)return slug;const [url]=matches[0],row=known.get(url);resolve(row,'flv',proof);return new URL(url).pathname.replaceAll('/','');
}
module.exports={resolve,canonicalSlug};
