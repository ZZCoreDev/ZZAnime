'use strict';
const assert=require('assert/strict'),{record}=require('./observed_chapter.cjs');
const policy={mp4upload:['mp4upload.com']};
for(const [slug,title] of [['psyren','Psyren'],['dark-summoner-to-dekiteiru','Dark Summoner to Dekiteiru']]){
 const row={url:'https://jkanime.net/'+slug+'/',title};
 const html='<title>'+title+' Episodio 4</title><script>var servers = '+JSON.stringify([{server:'Mp4upload',remote:Buffer.from('https://www.mp4upload.com/embed-example.html').toString('base64')}])+';</script>';
 const got=record(html,row,4,policy);assert.deepEqual(got.listing.episodes,[row.url+'4/']);assert.equal(got.listing.listingScope,'single-observed-chapter');assert.equal(got.episode.playbackVerified,false);
 assert.throws(()=>record(html,row,5,policy),/identity/);assert.throws(()=>record(html,{...row,title:'Another series'},4,policy),/identity/);assert.throws(()=>record(html,row,4,{}),/approved/);
 assert.throws(()=>record(html,{...row,url:'https://external.invalid/'},4,policy),/canonical/);
}
console.log('Two-series observed chapter identity, number, origin and provider checks PASS');
