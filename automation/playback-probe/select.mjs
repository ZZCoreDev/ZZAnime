// Pure logic of the daily playback probe: which chapters to open and how results accumulate.
import fs from 'node:fs';import path from 'node:path';import zlib from 'node:zlib';
export const FAMILIES=['streamwish','vidhide','mp4upload','yourupload','mega','voe'];
export const PER_FAMILY=2,MAX_EMBEDS=12;
const read=(dir,name)=>{try{return JSON.parse(fs.readFileSync(path.join(dir,name)))}catch{return null}};
// Episodes of one signed channel (root, voe/ or extra/), straight from the published files the apps read.
export function channelEpisodes(assets,prefix=''){
 const channel=read(assets,prefix+'channel.json');if(!channel)return [];
 const index=read(assets,prefix+JSON.parse(channel.payload).indexPath);const out=[];
 for(const row of Object.values(index?.series||{})){
  try{out.push(...JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(assets,prefix+row.path))).toString()).episodes)}catch{}
 }
 return out;
}
// The URL the app opens for an option (StreamWish through its player mirror, MEGA as embed).
export function embed(option){
 const u=option.url;let m;
 if(option.family==='streamwish'&&(m=/^https:\/\/[^/]+\/e\/([a-z0-9]{8,16})$/i.exec(u)))return 'https://hanerix.com/e/'+m[1];
 if(option.family==='mega'&&(m=/^https:\/\/(?:www\.)?mega\.nz\/(?:file|embed)\/([A-Za-z0-9_-]{8})#([A-Za-z0-9_-]{43})$/.exec(u)))return 'https://mega.nz/embed/'+m[1]+'#'+m[2];
 if(option.family==='mega'&&(m=/^https:\/\/(?:www\.)?mega\.nz\/(?:embed)?#!([A-Za-z0-9_-]{8})!([A-Za-z0-9_-]{43})$/.exec(u)))return 'https://mega.nz/embed/'+m[1]+'#'+m[2];
 return /^https:\/\//.test(u)?u:null;
}
// Two most recent chapters per family, each a different chapter; at most 12 embeds a day.
export function pick(episodes){
 const sorted=[...episodes].sort((a,b)=>String(b.observedAt).localeCompare(String(a.observedAt))),out=[];
 for(const family of FAMILIES){
  const seen=new Set();
  for(const ep of sorted){
   if(seen.size>=PER_FAMILY)break;if(seen.has(ep.url))continue;
   const option=[...(ep.options||[]),...(ep.extraOptions||[])].find(o=>o.family===family&&embed(o));
   if(option){seen.add(ep.url);out.push({family,episode:ep.url,observedAt:ep.observedAt,name:option.name,url:option.url,embed:embed(option)});}
  }
 }
 return out.slice(0,MAX_EMBEDS);
}
// One state per family and day: ok (one played), failed (none played, none blocked), blocked (GitHub IPs
// refused), no-sample. failingDays counts consecutive failed days; blocked and no-sample do not change it.
export function merge(previous,results,day,checkedAt){
 const families={};
 for(const family of FAMILIES){
  const rows=results.filter(r=>r.family===family),prev=previous?.families?.[family]||{};
  const state=!rows.length?'no-sample':rows.some(r=>r.state==='played')?'ok':rows.every(r=>r.state==='blocked-from-github')?'blocked':'failed';
  let failingDays=prev.failingDays||0;
  if(state==='ok')failingDays=0;else if(state==='failed'&&prev.day!==day)failingDays+=1;else if(state==='failed'&&prev.day===day)failingDays=Math.max(1,failingDays);
  families[family]={day,state,failingDays,...(state==='ok'?{lastOkAt:checkedAt}:prev.lastOkAt?{lastOkAt:prev.lastOkAt}:{}),results:rows.map(({family,...r})=>r)};
 }
 return {schema:1,checkedAt,aiCalls:0,maxEmbedsPerDay:MAX_EMBEDS,families};
}
