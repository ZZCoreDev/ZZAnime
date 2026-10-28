"""Public AniList evidence refresh. No model calls, APK keys, paid services or app mutations."""
import argparse,datetime,gzip,http.client,json,os,re,time,urllib.request,urllib.error
from pathlib import Path
QUERY='query($ids:[Int]){Page(page:1,perPage:50){media(id_in:$ids,type:ANIME){id title{romaji english native} synonyms format seasonYear coverImage{extraLarge large medium} studios(isMain:true){nodes{name}}}}}'
FORMATS={'TV','TV_SHORT','MOVIE','OVA','ONA','SPECIAL','MUSIC'}
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(path)
def validate(media,allowed):
 identity=media.get('id');url=media.get('coverImage',{}).get('extraLarge','')
 if type(identity)!=int or identity not in allowed:raise ValueError('Unexpected AniList identity')
 if media.get('format') not in FORMATS or media.get('seasonYear') is not None and (type(media['seasonYear'])!=int or not 1900<=media['seasonYear']<=2100):raise ValueError('Invalid metadata schema')
 if not isinstance(media.get('title'),dict) or not any(media['title'].values()) or any(v is not None and (not isinstance(v,str) or len(v)>2000) for v in media['title'].values()):raise ValueError('Invalid title')
 if len(media.get('synonyms',[]))>200 or any(not isinstance(x,str) or len(x)>2000 for x in media.get('synonyms',[])):raise ValueError('Invalid aliases')
 if not re.fullmatch(r'https://s[1-4][.]anilist[.]co/file/anilistcdn/media/anime/cover/(?:large|medium|small)/[a-z]*'+str(identity)+r'[-.][A-Za-z0-9_.-]+',url):raise ValueError('Cover does not belong to identity')
 studios=media.get('studios',{}).get('nodes')
 if not isinstance(studios,list) or len(studios)>100 or any(not isinstance(x.get('name'),str) or len(x['name'])>500 for x in studios):raise ValueError('Invalid studio metadata')
 return media
def fetch_once(ids):
 request=urllib.request.Request('https://graphql.anilist.co',data=json.dumps({'query':QUERY,'variables':{'ids':ids}}).encode(),headers={'Content-Type':'application/json','User-Agent':'ZZAnime-CatalogueEvidence/1.0'})
 with urllib.request.urlopen(request,timeout=35) as response:
  if response.geturl()!='https://graphql.anilist.co':raise ValueError('Unexpected API redirect')
  raw=response.read(4*1024*1024+1)
 if len(raw)>4*1024*1024:raise ValueError('Response limit')
 doc=json.loads(raw)
 if doc.get('errors'):raise ValueError('AniList returned errors; retain existing data')
 items=doc['data']['Page']['media'];seen=set()
 for media in items:
  if type(media.get('id'))!=int or media['id'] not in ids or media['id'] in seen:raise ValueError('Unexpected or duplicate identity')
  seen.add(media['id'])
 return items
def fetch(ids):
 for attempt in range(3):
  try:return fetch_once(ids)
  except urllib.error.HTTPError:raise
  except (TimeoutError,urllib.error.URLError,http.client.IncompleteRead):
   if attempt==2:raise
   time.sleep(5*(attempt+1))
def run(state,seed,proof=False,request=fetch,clock=time.time,pause=time.sleep):
 state.mkdir(parents=True,exist_ok=True);allowed=set(seed['ids']);ids=seed['proofIds'] if proof else sorted(allowed);path=state/'metadata.json'
 data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema':1,'items':{}}
 if data.get('schema')!=1:raise ValueError('State schema')
 now=int(clock());last=state/'last-run.json';heldpath=state/'held.json';held=json.loads(heldpath.read_text(encoding='utf-8')) if heldpath.exists() else {}
 if last.exists():
  previous=json.loads(last.read_text(encoding='utf-8'))
  retry=previous.get('retryAt',0)
  if previous.get('reason')=='TimeoutError' and not previous.get('policyVersion'):retry=min(retry,previous['checkedAt']+60)
  if previous.get('state')=='failed' and retry>now:return dict(previous,state='paused')
 due=[i for i in ids if (proof or now-data['items'].get(str(i),{}).get('checkedAt',0)>=86400) and held.get(str(i),{}).get('retryAt',0)<=now];changed=0;fetched=0;attempted=0;deadline=time.monotonic()+420
 try:
  for offset in range(0,len(due),25):
   if time.monotonic()>=deadline:break
   batch=due[offset:offset+25];items=request(batch);returned=set()
   attempted+=len(batch)
   for media in items:
    if type(media.get('id'))!=int or media['id'] not in batch or media['id'] in returned:raise ValueError('Unexpected or duplicate batch identity')
    returned.add(media['id']);key=str(media['id'])
    try:validate(media,allowed)
    except (ValueError,TypeError,KeyError):held[key]={'reason':'metadata_schema_requires_review','checkedAt':now,'retryAt':now+86400};continue
    changed+=data['items'].get(key,{}).get('media')!=media;data['items'][key]={'checkedAt':now,'media':media};fetched+=1;held.pop(key,None)
   for identity in set(batch)-returned:held[str(identity)]={'reason':'identity_not_returned','checkedAt':now,'retryAt':now+86400}
   save(path,data);save(heldpath,held)
   if offset+25<len(due):pause(3)
  if proof and fetched!=2:raise ValueError('Two real identities required for proof')
  raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();temp=state/'metadata.json.gz.tmp';temp.write_bytes(gzip.compress(raw,mtime=0));temp.replace(state/'metadata.json.gz')
  report={'state':'complete' if attempted==len(due) else 'partial','checkedAt':now,'proof':proof,'fetched':fetched,'changed':changed,'held':len(held),'cached':len(ids)-len(due),'requested':attempted,'unattempted':len(due)-attempted,'stored':len(data['items']),'aiCalls':0,'apkPublished':False,'retryAt':now+(86400 if attempted==len(due) else 3600),'policyVersion':2}
 except Exception as error:
  delay=3600 if isinstance(error,(TimeoutError,urllib.error.URLError,http.client.IncompleteRead)) and not isinstance(error,urllib.error.HTTPError) else 86400
  if isinstance(error,urllib.error.HTTPError) and error.code==429:
   try:delay=max(delay,int(error.headers.get('Retry-After','86400')))
   except ValueError:pass
  report={'state':'failed','checkedAt':now,'proof':proof,'fetched':fetched,'changed':changed,'aiCalls':0,'retainedPrevious':True,'reason':type(error).__name__,'retryAt':now+delay,'policyVersion':2};save(state/'failures'/str(now).zfill(12)/'failure.json',report);save(state/'last-run.json',report);(state/'ESTADO.md').write_text('Recogida de evidencias pendiente: '+report['reason']+'. Se conserva el estado anterior; reintento programado, sin IA.\n',encoding='utf-8');raise
 save(state/'last-run.json',report);(state/'ESTADO.md').write_text('Recogida de evidencias completada. Cambios: '+str(changed)+'. Validación y publicación Android quedan a cargo del supervisor local, sin IA.\n',encoding='utf-8');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--proof',action='store_true');args=p.parse_args();print(json.dumps(run(Path(os.environ['ZZ_CATALOGUE_STATE']),json.loads(Path(__file__).with_name('seed.json').read_text()),args.proof)))
