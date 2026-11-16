"""16/11/2026 (Robin): signed /latino/ complement with Latin American Spanish dubbed links (es-LA) of JK series.

Source: the PC's latino copy of animeav1.com (work/animeav1/latino.mjs), sent as one batch in branch latino-import of
the private data repo and imported by provider-renew (sample_group latino-import). Like /voe/ and /extra/, it lives in
its own state (latino-state) and never touches the root JK state or its dates. Every link must:
 - belong to a JK series of catalogue.json and to a chapter address of that series (series + number + /);
 - be one of the allowed families on its own host, with a strict address shape;
 - be approved by the app's real validator (RuntimeOptionAudit), the same one the JK import uses.
Each published chapter carries `options` with family, name, url and lang 'es-LA'. Only app 204+ reads /latino/."""
from pathlib import Path
import datetime,gzip,json,os,re,subprocess,tempfile
from archive_state import load,save,merge,stamp
FOLDER='latino-state'
LIMIT=5000
FRESH=7*86400
# name -> (family, strict link shape). Only the families the PC copy keeps from animeav1.
ALLOWED={
 'VOE':('voe',r'https://(?:voe\.sx|ashleyhardat\.com)/e/[A-Za-z0-9]{6,40}'),
 'Filemoon':('filemoon',r'https://(?:filemoon\.sx|bysekoze\.com)/e/[A-Za-z0-9]{6,40}'),
 'Mp4upload':('mp4upload',r'https://www\.mp4upload\.com/embed-[A-Za-z0-9]{6,40}\.html'),
 'Streamtape':('streamtape',r'https://(?:streamtape\.com|advtpe\.com)/e/[A-Za-z0-9]{6,40}/?'),
}
SERIES=r'https://jkanime\.net/[A-Za-z0-9_-][A-Za-z0-9_.-]*/'
def catalogue():return {r['url']:r for r in json.loads(Path(__file__).with_name('catalogue.json').read_bytes())}
def candidates(batch,now,known=None):
 """Checked chapters of a PC batch: ({url: episode}, {parent: listing}, {url: reason held}). No network."""
 if not isinstance(batch,dict) or batch.get('schema')!=1 or not isinstance(batch.get('series'),dict):raise ValueError('Invalid latino batch')
 known=known if known is not None else catalogue();episodes={};listings={};held={};total=0
 for parent,row in batch['series'].items():
  if not re.fullmatch(SERIES,parent) or parent not in known or not isinstance(row,dict):held[str(parent)[:200]]='Series not in the JK catalogue';continue
  for url,ep in (row.get('episodes') or {}).items():
   total+=1
   if total>LIMIT:raise ValueError('Bounded import exceeded')
   if not isinstance(url,str) or not re.fullmatch(re.escape(parent)+r'[1-9][0-9]{0,4}/',url):held[str(url)[:200]]='Invalid chapter address';continue
   when=ep.get('checkedAt') if isinstance(ep,dict) else None
   if not 0<=now.timestamp()-stamp(when)<=FRESH:held[url]='Stale or future observation';continue
   providers={}
   for o in ep.get('options') or []:
    # 16/11 (Robin): Spanish from Spain (es-ES, castellano) travels the same way; each link keeps its own language.
    if not isinstance(o,dict) or o.get('lang') not in ('es-LA','es-ES'):continue
    name,link=o.get('name'),o.get('url')
    rule=ALLOWED.get(name)
    if not rule or not isinstance(link,str) or not re.fullmatch(rule[1],link):continue
    p=providers.setdefault(name,{'name':name,'family':rule[0],'links':[]})
    if link not in p['links'] and len(p['links'])<4:p['links'].append(link);p.setdefault('langs',{})[link]=o['lang']
   if not providers:held[url]='No allowed latino link';continue
   episodes[url]={'episode':url,'observedAt':when,'complete':True,'lang':'es-LA','providers':list(providers.values())}
   listing=listings.setdefault(parent,{'observedAt':when,'complete':True,'title':known[parent]['title'],'episodes':[]})
   listing['episodes']=sorted(set(listing['episodes'])|{url});listing['observedAt']=max(listing['observedAt'],when,key=stamp)
 return episodes,listings,held
def approve(episodes,check):
 """Keeps only links the app validator approves; check({key:{name,url}}) -> {key: bool}. Chapters left empty are dropped."""
 import run as p
 queries={p.sha((pr['name']+'\0'+u).encode()):{'name':pr['name'],'url':u} for ep in episodes.values() for pr in ep['providers'] for u in pr['links']}
 approved=check(queries) if queries else {};out={};held={}
 for url,ep in episodes.items():
  providers=[{**pr,'links':[u for u in pr['links'] if approved.get(p.sha((pr['name']+'\0'+u).encode()))]} for pr in ep['providers']]
  providers=[pr for pr in providers if pr['links']]
  if providers:out[url]={**ep,'providers':providers}
  else:held[url]='No app-approved latino link'
 return out,held
def java_check(queries):
 import run as p
 with tempfile.TemporaryDirectory() as temp:
  # modern=True: the validator of the apps that read complements (the one /voe/ uses); only app 204+ reads /latino/.
  cp=p.compile_java(Path(temp)/'classes',modern=True)
  output=p.command(['java','-cp',cp,'tv.jkanime.web.RuntimeOptionAudit'],input='\n'.join(json.dumps(v) for v in queries.values()))
 return {r['key']:r['approved'] for r in map(json.loads,output.splitlines())}
def import_batch(folder,batch_path,now=None,check=java_check):
 folder=Path(folder);now=now or datetime.datetime.now(datetime.timezone.utc);raw=Path(batch_path).read_bytes()
 batch=json.loads(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw)
 episodes,listings,held=candidates(batch,now)
 episodes,held2=approve(episodes,check);held.update(held2)
 side=load(folder/FOLDER);before={u:e['observedAt'] for u,e in side['episodes'].items()}
 incoming={'episodes':{u:e for u,e in episodes.items() if stamp(e['observedAt'])>stamp(before.get(u))},'listings':{}}
 for u in incoming['episodes']:parent=u.rsplit('/',2)[0]+'/';incoming['listings'][parent]=listings[parent]
 if incoming['episodes']:merge(side,incoming);save(folder/FOLDER,side,set(incoming['listings']))
 import hashlib
 report={'batchSha256':hashlib.sha256(raw).hexdigest(),'checkedAt':now.isoformat(),'state':'imported' if incoming['episodes'] else 'unchanged','imported':len(incoming['episodes']),'series':len(incoming['listings']),'held':dict(list(held.items())[:200]),'heldCount':len(held)}
 (folder/'latino-import-status.json').write_text(json.dumps(report,indent=1),encoding='utf-8')
 return report
def build(state,now,sha,raw):
 rows={}
 for url,ep in state['episodes'].items():
  parent=url.rsplit('/',2)[0]+'/';listing=state['listings'].get(parent)
  if not listing or url not in listing.get('episodes',[]) or not ep.get('complete') or now.timestamp()-stamp(ep.get('observedAt'))<0:continue
  options=[{'family':pr['family'],'name':pr['name'],'url':u,'lang':(pr.get('langs') or {}).get(u,'es-LA')} for pr in ep.get('providers',[]) if pr.get('name') in ALLOWED for u in pr.get('links',[]) if re.fullmatch(ALLOWED[pr['name']][1],u)]
  if options:rows.setdefault(parent,[]).append({'url':url,'observedAt':ep['observedAt'],'playbackVerified':False,'lang':'es-LA','options':options})
 index={'schema':1,'createdAt':now.isoformat().replace('+00:00','Z'),'playbackVerified':False,'lang':'es-LA','series':{},'feed':{'schema':1,'episodes':[]}};files={}
 for parent,eps in sorted(rows.items()):
  listing=state['listings'][parent]
  body=raw({'schema':1,'series':parent,'lang':'es-LA','listedAt':listing['observedAt'],'listedEpisodes':listing['episodes'],'episodes':sorted(eps,key=lambda e:e['url']),'playbackVerified':False})
  packed=gzip.compress(body,mtime=0);h=sha(packed);name='series/'+h+'.bin'
  if max(len(body),len(packed))>2097152:continue
  files[name]=packed;index['series'][sha(parent.encode())]={'path':name,'sha256':h,'bytes':len(packed),'expandedBytes':len(body),'episodes':len(eps)}
 return index,files
def render(folder,now,key):
 """Files under latino/ for the static site, or {} when there is nothing to publish."""
 import run as p
 from cryptography.hazmat.primitives import hashes
 from cryptography.hazmat.primitives.asymmetric import padding
 state=load(Path(folder)/FOLDER)
 if not state['episodes']:return {}
 index,files=build(state,now,p.sha,p.raw)
 if not index['series']:return {}
 body=p.raw(index);digest=p.sha(body);name='indexes/'+digest+'.bin';files[name]=body
 payload=p.raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':now.isoformat().replace('+00:00','Z'),'indexSha256':digest,'indexPath':name,'indexBytes':len(body),'mode':'daily-new','lang':'es-LA'})
 files['channel.json']=p.raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})
 return {'latino/'+n:b for n,b in files.items()}
def main(publish=False):
 import sys
 folder=Path(os.environ['ZZ_DATA']);report=import_batch(folder,os.environ['ZZ_LATINO_BATCH'])
 if report['imported'] and publish:
  subprocess.run([sys.executable,str(Path(__file__).with_name('run.py')),'--publish'],check=True);report['published']=True
  (folder/'latino-import-status.json').write_text(json.dumps(report,indent=1),encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k!='held'}))
