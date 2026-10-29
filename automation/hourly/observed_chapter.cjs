'use strict';
const parser=require('./lib/fast-rules.cjs'),rules=require('./lib/backup-rules.cjs');
// A live chapter proves this chapter only. Never claim to have enumerated the series.
function record(html,row,number,policy){
 const url=row.url+number+'/';
 if(!Number.isInteger(number)||number<1||rules.series(row.url)!==row.url||rules.episode(url,row.url)!==url)throw Error('Invalid canonical chapter');
 parser.identity(html,row.observed_title||row.title,number);
 const data=parser.providers(html,policy);
 if(!data.complete||!data.providers.some(p=>p.links.length))throw Error('No independent approved option');
 const observedAt=new Date().toISOString();
 return {listing:{series:row.url,title:row.observed_title||row.title,observedAt,episodes:[url],complete:true,listingScope:'single-observed-chapter',listingEvidence:'live-chapter-title-number-and-options',playbackVerified:false},episode:{archiveVersion:3,episode:url,observedAt,...data,playbackVerified:false}};
}
module.exports={record};
