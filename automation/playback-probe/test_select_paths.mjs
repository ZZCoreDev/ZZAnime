import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {test} from 'node:test';
import {gzipSync} from 'node:zlib';
import {channelEpisodes} from './select.mjs';

test('published main and complement layouts preserve valid episodes', () => {
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'zzprobe-'));
 try{
  const indexPath='indexes/'+'a'.repeat(64)+'.bin';
  const seriesPath='series/'+'b'.repeat(64)+'.bin';
  for(const prefix of ['', 'voe/', 'extra/']){
   const directory=path.join(root,prefix);
   fs.mkdirSync(path.join(directory,'indexes'),{recursive:true});
   fs.mkdirSync(path.join(directory,'series'),{recursive:true});
   fs.writeFileSync(path.join(directory,'channel.json'),JSON.stringify({payload:JSON.stringify({indexPath})}));
   fs.writeFileSync(path.join(directory,indexPath),JSON.stringify({series:{first:{path:seriesPath}}}));
   fs.writeFileSync(path.join(directory,seriesPath),gzipSync(JSON.stringify({episodes:[{url:'test-episode'}]})));
   assert.deepEqual(channelEpisodes(root,prefix),[{url:'test-episode'}]);
  }
  const manifest=path.join(root,'channel.json');
  fs.writeFileSync(manifest,JSON.stringify({payload:JSON.stringify({indexPath:'.'})}));
  assert.deepEqual(channelEpisodes(root),[]);
  fs.writeFileSync(manifest,JSON.stringify({payload:'invalid'}));
  assert.deepEqual(channelEpisodes(root),[]);
  assert.deepEqual(channelEpisodes(root,'not-a-channel/'),[]);
 }finally{
  fs.rmSync(root,{recursive:true,force:true});
 }
});
