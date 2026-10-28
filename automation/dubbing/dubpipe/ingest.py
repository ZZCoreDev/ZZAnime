from __future__ import annotations
import dataclasses,json,shutil,zipfile
from pathlib import Path
from .core import Episode,canonical_hash,download,digest,media_info,read
def discover(document:dict,config:dict|None=None,root:Path|None=None)->list[Episode]:
 episodes=[]
 for source in document.get('sources',[]):
  if not source.get('enabled',False):continue
  if source.get('kind')=='json_manifest':
   if not config or not root:raise ValueError('Owned manifest requires explicit host allowlist and cache directory')
   file=root/(canonical_hash(source['manifest_url'])+'.json');download(source['manifest_url'],file,config['allowed_hosts'],2*1024*1024);rows=read(file).get('episodes',[])
  elif source.get('kind')=='direct':rows=source.get('episodes',[])
  else:raise ValueError('Only authorized direct files/owned JSON manifests are supported; no restricted-platform scraping')
  if not isinstance(rows,list) or len(rows)>1000:raise ValueError('Manifest episode count outside limits')
  for row in rows:
   if not isinstance(row,dict):raise ValueError('Manifest entry schema')
   identity=row.get('id') if isinstance(row.get('id'),str) else 'invalid-'+canonical_hash(row)[:16]
   episodes.append(Episode(id=identity,series=source.get('series',''),title=row.get('title',''),url=row.get('url',''),language=row.get('language','ja'),provenance=source.get('provenance',{}),archive_member=row.get('archive_member',''),local_file=row.get('local_file','')))
 return episodes
def execute(episode:Episode,out:Path,config:dict)->dict:
 episode.validate();target=out/'original.mp4'
 if episode.local_file:
  if not config.get('allow_local_inputs'):raise ValueError('Local input disabled outside local test profile')
  shutil.copyfile(episode.local_file,target)
 else:
  file=out/('source.zip' if episode.archive_member else 'source.mp4');download(episode.url,file,config['allowed_hosts'],config['max_download_mb']*1024*1024)
  if episode.archive_member:
   with zipfile.ZipFile(file) as archive:
    info=archive.getinfo(episode.archive_member)
    if info.is_dir() or info.file_size>config['max_download_mb']*1024*1024 or Path(info.filename).name!=info.filename:raise ValueError('Unsafe archive member')
    with archive.open(info) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
  else:file.replace(target)
 info=media_info(target)
 if info['duration']>config['max_episode_seconds'] or not info['audio_streams'] or not info['video_streams']:raise ValueError('Media outside configured duration/stream limits')
 return {'video':'original.mp4','sha256':digest(target),'duration':info['duration'],'provenance':episode.provenance}
