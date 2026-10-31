"""Signed /extra/ complement for chapters whose only valid servers are new families (móvil 93+/TV 117+).

Chapters observed with no regular provider but with extraProviders (YourUpload, MixDrop on new hosts)
are kept in extra-state, never in the root state, so root records and their dates are never replaced.
/extra/channel.json mirrors the root channel (same key, index, immutable shards); each chapter carries
`options: []` and `extraOptions`. Installed apps never read it."""
from pathlib import Path
import copy,gzip,json,time
from archive_state import load,save,merge,stamp
import extra_options
FOLDER='extra-state'
def split(folder,incoming):
 # Moves extra-only chapters out of `incoming`; extraProviders on chapters with regular providers stay put.
 rest=copy.deepcopy(incoming);extra={'episodes':{},'listings':{}};now=time.time()
 for url,ep in incoming.get('episodes',{}).items():
  regular=[p for p in ep.get('providers',[]) if p.get('family')!='voe' and p.get('links')]
  if regular or not ep.get('extraProviders'):continue
  parent=url.rsplit('/',2)[0]+'/';listing=incoming.get('listings',{}).get(parent)
  if listing and listing.get('complete') and url in listing.get('episodes',[]) and ep.get('complete') and 0<=now-stamp(ep.get('observedAt'))<=7*86400:
   extra['episodes'][url]={**ep,'providers':[]};extra['listings'][parent]=listing
  rest['episodes'][url].pop('extraProviders',None)
  if not ep.get('providers'):rest['episodes'].pop(url)
 if not extra['episodes']:return rest,0
 side=load(Path(folder)/FOLDER)
 for url,ep in list(extra['episodes'].items()):
  old=side['episodes'].get(url)
  if old and stamp(old.get('observedAt'))>=stamp(ep.get('observedAt')):extra['episodes'].pop(url)
 if extra['episodes']:merge(side,extra);save(Path(folder)/FOLDER,side,set(extra['listings']))
 return rest,len(extra['episodes'])
def build(state,now,dead,sha,raw,titles=None):
 rows={}
 for url,ep in state['episodes'].items():
  parent=url.rsplit('/',2)[0]+'/';listing=state['listings'].get(parent)
  if not listing or url not in listing.get('episodes',[]) or not ep.get('complete') or now.timestamp()-stamp(ep.get('observedAt'))<0:continue
  extra=extra_options.build(ep,dead,set(),sha)
  if extra:rows.setdefault(parent,[]).append({'url':url,'observedAt':ep['observedAt'],'playbackVerified':False,'options':[],'extraOptions':extra})
 index={'schema':1,'createdAt':now.isoformat().replace('+00:00','Z'),'playbackVerified':False,'series':{},'feed':{'schema':1,'episodes':[]}};files={}
 for parent,eps in sorted(rows.items()):
  listing=state['listings'][parent]
  body=raw({'schema':1,'series':parent,'listedAt':listing['observedAt'],'listedEpisodes':listing['episodes'],'episodes':sorted(eps,key=lambda e:e['url']),'playbackVerified':False})
  packed=gzip.compress(body,mtime=0);h=sha(packed);name='series/'+h+'.bin'
  if max(len(body),len(packed))>2097152:continue
  files[name]=packed;index['series'][sha(parent.encode())]={'path':name,'sha256':h,'bytes':len(packed),'expandedBytes':len(body),'episodes':len(eps)}
 return index,files
def render(folder,now,key,dead):
 """Files under extra/ for the static site, or {} when there is nothing to publish."""
 import run as p
 from cryptography.hazmat.primitives import hashes
 from cryptography.hazmat.primitives.asymmetric import padding
 state=load(Path(folder)/FOLDER)
 if not state['episodes']:return {}
 # Drop stored extra links that are no longer valid (mixdroop.bz, a parked look-alike) (a chapter left with none is simply not published).
 changed=set()
 for url,ep in list(state['episodes'].items()):
  kept=extra_options.prune(ep)
  if kept is ep:continue
  changed.add(url.rsplit('/',2)[0]+'/')
  state['episodes'][url]=kept
 if changed:save(Path(folder)/FOLDER,state,changed)
 index,files=build(state,now,dead,p.sha,p.raw)
 if not index['series']:return {}
 body=p.raw(index);digest=p.sha(body);name='indexes/'+digest+'.bin';files[name]=body
 payload=p.raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':now.isoformat().replace('+00:00','Z'),'indexSha256':digest,'indexPath':name,'indexBytes':len(body),'mode':'daily-new'})
 files['channel.json']=p.raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})
 return {'extra/'+n:b for n,b in files.items()}
