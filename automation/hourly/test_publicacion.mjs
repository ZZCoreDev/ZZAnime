// 12/11 (décima revisión R10-01): a fake publication like the real one for the channel tests. Each prefix ('', 'voe/',
// 'extra/') has its own channel.json → indexes/<sha>.bin → series[key] = {path: 'series/<file>.bin'}; a file only exists
// when it is in the current index. add() publishes a new index version (like a new publication).
import {createHash} from 'node:crypto';
const sha=t=>createHash('sha256').update(t).digest('hex');
export function publication(){
 const files={'':new Map(),'voe/':new Map(),'extra/':new Map()};let version=0;
 const indexPath=()=>'indexes/'+sha('v'+version)+'.bin';
 return {
  // series key and file name of one series in one prefix
  add(prefix,file,seriesKey){files[prefix].set(file,seriesKey);version++;},
  remove(prefix,file){files[prefix].delete(file);version++;},
  key:name=>sha('serie:'+name),
  fetch(request){const p=new URL(request.url).pathname.slice(1),m=/^((?:voe|extra)\/)?(.*)$/.exec(p),prefix=m[1]||'',rest=m[2];
   if(rest==='channel.json')return new Response(JSON.stringify({payload:JSON.stringify({schema:1,indexPath:indexPath()}),signature:'x'}));
   if(rest===indexPath()){const series={};for(const [file,key] of files[prefix])series[key]={path:file};return new Response(JSON.stringify({schema:1,series}));}
   if(rest.startsWith('series/')&&files[prefix].has(rest))return new Response('file');
   return new Response('not found',{status:404});}
 };
}
