'use strict';
const crypto=require('crypto');
const key=value=>crypto.createHash('sha256').update(value).digest('hex');
function series(raw){try{const u=new URL(raw);return u.protocol==='https:'&&['jkanime.net','www.jkanime.net'].includes(u.hostname)&&!u.username&&!u.password&&!u.port&&!u.search&&!u.hash&&/^\/[a-zA-Z0-9_-]+\/?$/.test(u.pathname)?'https://jkanime.net'+u.pathname.replace(/\/$/,'')+'/':''}catch{return ''}}
function episode(raw,parent){try{const u=new URL(raw);return u.protocol==='https:'&&['jkanime.net','www.jkanime.net'].includes(u.hostname)&&!u.username&&!u.password&&!u.port&&!u.search&&!u.hash&&/^\/[a-zA-Z0-9_-]+\/[1-9][0-9]*\/?$/.test(u.pathname)&&(!parent||series('https://jkanime.net'+u.pathname.replace(/\/[0-9]+\/?$/,'/'))===series(parent))?'https://jkanime.net'+u.pathname.replace(/\/$/,'')+'/':''}catch{return ''}}
// AnimeFLV labels StreamWish as «SW»; the app only knows «Streamwish», so the name is normalised before use.
function canonical(n){return /^sw(?:[\s0-9:()_-].*)?$/i.test((n||'').trim())?'Streamwish':n}
function family(n){n=(canonical(n)||'').trim().toLowerCase();const m=n.match(/^(desu|magi|mega|streamwish|vidhide|mixdrop|mp4upload|voe|streamtape?)(?:[\s0-9:()_-].*)?$/);return m?m[1].replace(/^streamtap$/,'streamtape'):''}
function embed(raw,roots){try{const u=new URL(raw);return raw.length<=8192&&u.protocol==='https:'&&!u.username&&!u.password&&!u.port&&roots.some(h=>u.hostname===h||u.hostname.endsWith('.'+h))?u.href:''}catch{return ''}}
function resourceAllowed(type,raw,scripts){try{const u=new URL(raw);if(u.protocol!=='https:'||u.username||u.password||u.port||/\.(?:m3u8|mpd|mp4|m4s|m4v|mkv|webm|ts|aac|m4a|mp3|mov|ogg)$/i.test(u.pathname))return false;const jk=['jkanime.net','www.jkanime.net'].includes(u.hostname);if(type==='document')return jk;if(type==='script')return scripts.some(h=>u.hostname===h||u.hostname.endsWith('.'+h));return ['fetch','xhr'].includes(type)&&jk&&u.pathname.startsWith('/ajax/')}catch{return false}}
module.exports={key,series,episode,family,canonical,embed,resourceAllowed};
