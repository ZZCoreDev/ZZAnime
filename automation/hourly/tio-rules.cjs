'use strict';
const p=require('./lib/fast-rules.cjs'),r=require('./lib/backup-rules.cjs');
function array(html,name){const m=new RegExp('(?:var|let|const)\\s+'+name+'\\s*=\\s*').exec(html);if(!m)throw Error('Missing observed '+name);const x=p.jsonValue(html,m.index+m[0].length);if(!Array.isArray(x))throw Error('Expected array');return x;}
function heading(html){const m=/<h1\b[^>]*>([\s\S]*?)<\/h1>/i.exec(html);if(!m)throw Error('Missing source heading');return m[1].replace(/<[^>]*>/g,'').replace(/&amp;/g,'&').replace(/&#39;|&apos;/g,"'").replace(/&quot;/g,'"').trim();}
function downloads(html){const seen=new Set(),out=[];for(const m of html.matchAll(/href=["'](https:\/\/(?:www\.)?mega\.nz\/(?:#![A-Za-z0-9_-]{8}![A-Za-z0-9_-]{43}|file\/[A-Za-z0-9_-]{8}#[A-Za-z0-9_-]{43}))["']/g)){if(!seen.has(m[1])){seen.add(m[1]);out.push({name:'Mega',family:'mega',url:m[1]});}}return out.slice(0,8);}
function record(detail,episode,row,number,policy,proof=false){
 const identity=require('./source-identities.cjs').resolve(row,'tio',proof);
 const info=array(detail,'anime_info'),numbers=array(detail,'episodes'),title=info[2],slug=info[1];
 if(!Number.isInteger(number)||number<1||number>100000||!numbers.every(n=>Number.isInteger(n)&&n>0&&n<=100000)||new Set(numbers).size!==numbers.length||!numbers.includes(number))throw Error('Unobserved chapter');
 if(!/^[a-zA-Z0-9_-]+$/.test(slug)||r.series(row.url)!==row.url||slug!==identity.slug||!p.normal(row.title)||p.normal(title)!==p.normal(identity.title)||p.normal(heading(detail))!==p.normal(title)||p.normal(heading(episode))!==p.normal(title+' '+number))throw Error('Ambiguous cross-source identity');
 const providers=[],held=[];
 for(const video of array(episode,'videos')){
  if(!Array.isArray(video)||typeof video[0]!=='string'||typeof video[1]!=='string')continue;
  const family=r.family(video[0]);if(!family){held.push('unapproved-family');continue;}
  const link=r.embed(video[1],policy[family]||[]);if(!link){held.push('unapproved-origin');continue;}
  providers.push({name:video[0],family,links:[link],playbackVerified:false});
 }
 if(!providers.length)throw Error('No existing app-approved provider family');
 const observedAt=new Date().toISOString(),sourceSeries='https://tioanime.com/anime/'+slug,sourceEpisode='https://tioanime.com/ver/'+slug+'-'+number;
 return {parent:row.url,listing:{series:row.url,title:row.title,episodes:numbers.map(n=>row.url+n+'/'),complete:true,observedAt,sourceSeries,identityEvidence:identity.alias?'verified-title-year-mapping+canonical-id+series-and-chapter-headings+observed-number':'unique-catalogue-title+identical-slug+source-series-and-chapter-headings+observed-number'},episode:{archiveVersion:3,episode:row.url+number+'/',observedAt,complete:true,providers,downloads:downloads(episode),sourceEpisode,sourceSeries,excludedOptions:held.length,playbackVerified:false}};
}
module.exports={array,heading,record,downloads};
