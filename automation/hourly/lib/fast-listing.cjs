'use strict';
const parser=require('./fast-rules.cjs');
async function listing(http,row){
 const html=await http.get(row.url);parser.identity(html,row.observed_title||row.title);
 const endpoint=/url:\s*['"](https:\/\/jkanime\.net\/ajax\/episodes\/[0-9]+\/)['"]\s*\+\s*pag/.exec(html),meta=/<meta[^>]+name=['"]csrf-token['"][^>]+content=['"]([^'"]+)['"]/i.exec(html);
 if(!endpoint||!meta||meta[1].length>256)throw Error('Listing requires browser review; existing data preserved');
 const size=Number(/var\s+paginationConf\s*=\s*([0-9]+)/.exec(html)?.[1]||16);if(size<1||size>200)throw Error('Unexpected page size');
 const urls=new Set();let pages=1;
 for(let page=1;page<=pages;page++){
  const raw=await http.get(endpoint[1]+page,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With':'XMLHttpRequest','Origin':'https://jkanime.net','Referer':row.url},body:new URLSearchParams({_token:meta[1]}).toString()}),data=JSON.parse(raw);
  if(!Array.isArray(data.data)||!Number.isInteger(Number(data.total))||Number(data.total)<0)throw Error('Invalid listing response');pages=Math.ceil(Number(data.total)/size);if(pages>200)throw Error('Listing exceeds bounded page limit');
  const before=urls.size;for(const ep of parser.episodeNumbers(data.data,row.url))urls.add(ep);if(page<pages&&urls.size===before)throw Error('Pagination repeated observations');
 }
 if(!urls.size)throw Error('No published episode records observed');
 return {sourceId:row.source_id,series:row.url,title:row.observed_title||row.title,observedAt:new Date().toISOString(),episodes:[...urls].sort((a,b)=>Number(a.match(/\/(\d+)\/$/)[1])-Number(b.match(/\/(\d+)\/$/)[1])),complete:true,listingEvidence:'observed-ajax-episode-records',playbackVerified:false};
}
module.exports={listing};
