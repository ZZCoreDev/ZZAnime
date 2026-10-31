'use strict';
const p=require('./lib/fast-rules.cjs'),r=require('./lib/backup-rules.cjs'),t=require('./tio-rules.cjs');
function episodeToken(detail,row,number,proof=false){
 const identity=require('./source-identities.cjs').resolve(row,'flv',proof),title=/^Ver (.+?) Sub espa[nñ]ol(?: latino)? Online$/i.exec(t.heading(detail))?.[1];
 const pages=t.array(detail,'eps'),selected=pages.filter(x=>Array.isArray(x)&&Number(x[0])===number),numbers=pages.map(x=>Number(x[0]));
 if(r.series(row.url)!==row.url||!Number.isInteger(number)||number<1||!title||p.normal(title)!==p.normal(identity.title)||!detail.includes('data-sl="'+identity.slug+'"')||selected.length!==1||selected[0][2]!==''||numbers.some(n=>!Number.isInteger(n)||n<1||n>100000)||new Set(numbers).size!==numbers.length)throw Error('Ambiguous AnimeFLV listing identity');
 const token=String(selected[0][0]);if(!/^0*[1-9][0-9]{0,5}$/.test(token)||token.length>6)throw Error('Invalid observed chapter token');return token;
}
function record(detail,episode,options,row,number,policy,proof=false,allowVoe=false){
 const token=episodeToken(detail,row,number,proof);
 const identity=require('./source-identities.cjs').resolve(row,'flv',proof),slug=identity.slug,heading=t.heading(detail),title=/^Ver (.+?) Sub espa[nñ]ol(?: latino)? Online$/i.exec(heading)?.[1];
 const pages=t.array(detail,'eps'),selected=pages.filter(x=>Array.isArray(x)&&Number(x[0])===number),numbers=pages.map(x=>Number(x[0]));
 if(r.series(row.url)!==row.url||!title||p.normal(title)!==p.normal(identity.title)||![number,token].some(n=>p.normal(t.heading(episode))===p.normal(identity.title+' episodio '+n))||!detail.includes('data-sl="'+slug+'"')||selected.length!==1||selected[0][2]!==''||numbers.some(n=>!Number.isInteger(n)||n<1||n>100000)||new Set(numbers).size!==numbers.length)throw Error('Ambiguous AnimeFLV chapter identity');
 const providers=[],reviewProviders=[],seen=new Set();let excluded=0;
 for(const m of options.matchAll(/<li\b[^>]*\bencrypt=["']([a-fA-F0-9]{2,8000})["'][^>]*>([\s\S]*?)<\/li>/g)){
  if(m[1].length%2){excluded++;continue;}const link=Buffer.from(m[1],'hex').toString('utf8'),name=r.canonical(/<span[^>]*>([^<]+)<\/span>/i.exec(m[2])?.[1]?.trim()),family=r.family(name);
  if(!family||r.embed(link,policy[family]||[])!==link){excluded++;continue;}if(seen.has(link))continue;seen.add(link);const provider={name,family,links:[link],playbackVerified:false};if(!['mp4upload','streamwish','vidhide',...(allowVoe?['voe']:[])].includes(family)){reviewProviders.push(provider);excluded++;continue;}providers.push(provider);
 }
 const rank=['mp4upload','streamwish','mixdrop','vidhide','streamtape','mega'];providers.sort((a,b)=>rank.indexOf(a.family)-rank.indexOf(b.family));if(!providers.length)throw Error('No existing approved provider');
 const observedAt=new Date().toISOString(),sourceSeries='https://vww.animeflv.one/anime/'+slug,sourceEpisode='https://vww.animeflv.one/ver/'+slug+'-'+token;
 return {parent:row.url,listing:{series:row.url,title:row.title,episodes:numbers.map(n=>row.url+n+'/'),complete:true,observedAt,sourceSeries,identityEvidence:identity.alias?'verified-title-year-mapping+canonical-id+series-heading+chapter-heading+observed-episode-array':'exact-catalogue-slug+series-heading+chapter-heading+observed-episode-array'},episode:{archiveVersion:3,episode:row.url+number+'/',observedAt,complete:true,providers,reviewProviders,sourceSeries,sourceEpisode,excludedOptions:excluded,playbackVerified:false}};
}
module.exports={record,episodeToken};
