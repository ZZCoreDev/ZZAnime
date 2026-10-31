"""Provider-page liveness of stored options: only positive deletion markers exclude, never a playback claim."""
from pathlib import Path
import hashlib,json,re,time,urllib.request,urllib.error
from archive_state import stamp
W=Path(__file__).resolve().parent
FAKE='zzzzzzzzzzzz'
GONE='File is no longer available as it expired or has been deleted.'
# Markers observed 30/10/2026 on real pages (fixtures in link-fixtures.json). Anything else is unknown.
DEAD={'mp4upload':lambda s,b:s==200 and b.strip()=='File was deleted',
 'streamwish':lambda s,b:s==200 and len(b)<4000 and GONE in b,
 'vidhide':lambda s,b:s==200 and len(b)<4000 and GONE in b,
 'voe':lambda s,b:s==404 and '<title>404 - Not found</title>' in b,
 # MEGA's public API: -9 no such file, -16 taken down; an existing file returns its size and attributes.
 'mega':lambda s,b:s==200 and b.strip() in ('[-9]','[-16]','-9','-16')}
ALIVE={'mp4upload':lambda s,b:s==200 and 'player.src(' in b and 'video/mp4' in b,
 'streamwish':lambda s,b:s==200 and 'jwplayer' in b and 'eval(function(p,a,c,k,e,d)' in b,
 'vidhide':lambda s,b:s==200 and 'jwplayer' in b and 'eval(function(p,a,c,k,e,d)' in b,
 'voe':lambda s,b:s==200 and '<title>Redirecting...</title>' in b and "window.location.href = 'https://" in b,
 'mega':lambda s,b:s==200 and '"s":' in b and '"at":' in b}
LINKS={'mp4upload':r'https://(?:www\.)?mp4upload\.com/embed-([a-z0-9]{8,16})\.html',
 'streamwish':r'https://(?:hgcloud\.to|streamwish\.(?:com|to))/e/([a-z0-9]{8,16})',
 'vidhide':r'https://(?:vidhidevip\.com|vidhidepro\.com|vidhide\.com|filelions\.top)/(?:embed|v)/([a-z0-9]{8,16})',
 'voe':r'https://voe\.sx/e/([a-zA-Z0-9]{8,16})',
 'mega':r'https://(?:www\.)?mega\.nz/(?:(?:file|embed)/([A-Za-z0-9_-]{8})#[A-Za-z0-9_-]{43}|(?:embed)?#!([A-Za-z0-9_-]{8})![A-Za-z0-9_-]{43})'}
MEGA_API='https://g.api.mega.co.nz/cs'
REPORTED_RECHECK=3600
# Device-reported links get their own slots on top of the regular ones, still inside the run's time budget.
REPORTED_LIMIT=10
INTERVAL={'alive':24*3600,'unknown':6*3600,'dead':1800,'excluded':48*3600}
CONFIRM_GAP=1800
def sha(b):return hashlib.sha256(b).hexdigest()
def policy():return json.loads((W/'link-health-policy.json').read_bytes())
def target(family,link,rules):
 m=re.fullmatch(LINKS.get(family,'(?!)'),link)
 if not m:return None
 # hgcloud.to only serves a JavaScript loader; its own script moves to this mirror, which shares the file ids.
 if family=='streamwish':return 'https://'+rules['mirrors']['streamwish']+'/e/'+m.group(1)
 if family=='mp4upload':return 'https://www.mp4upload.com/embed-'+m.group(1)+'.html'
 if family=='mega':return MEGA_API+'?id=0&file='+(m.group(1) or m.group(2))
 return link
class Manual(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kw):return None
def fetch(url,hops=1):
 if url.startswith(MEGA_API+'?'):
  # The file id only; the decryption key never leaves the stored link.
  req=urllib.request.Request(MEGA_API+'?id=0',data=json.dumps([{'a':'g','p':url.rsplit('=',1)[1]}]).encode(),headers={'Content-Type':'application/json','User-Agent':'ZZAnime-LinkCheck/1 (+https://github.com/ZZCoreDev/ZZAnime)'},method='POST')
  try:
   with urllib.request.urlopen(req,timeout=20) as r:return r.status,r.read(20000).decode('utf-8','replace')
  except urllib.error.HTTPError as e:return e.code,e.read(20000).decode('utf-8','replace')
 req=urllib.request.Request(url,headers={'User-Agent':'ZZAnime-LinkCheck/1 (+https://github.com/ZZCoreDev/ZZAnime)','Accept':'text/html'})
 try:
  with urllib.request.build_opener(Manual).open(req,timeout=20) as r:return r.status,r.read(300000).decode('utf-8','replace')
 except urllib.error.HTTPError as e:
  where=e.headers.get('Location','')
  # vidhidevip.com answers 301 to its current host with the same file id; follow exactly that, once.
  if e.code in (301,302) and hops and where.startswith('https://') and where.rstrip('/').rsplit('/',1)[-1]==url.rstrip('/').rsplit('/',1)[-1]:return fetch(where,hops-1)
  return e.code,e.read(300000).decode('utf-8','replace')
def classify(family,status,body):
 if family not in DEAD:return 'unknown'
 return 'dead' if DEAD[family](status,body) else 'alive' if ALIVE[family](status,body) else 'unknown'
def candidates(folder,now,rules):
 from voe_channel import load_parents
 # Only the shards of series in the 7-day news list, not the whole archive, on every 5-minute run.
 meta=Path(folder)/'observations.json';seen=json.loads(meta.read_bytes()).get('newsSeen',{}) if meta.exists() else {}
 news=[u for u,at in sorted(seen.items(),key=lambda r:str(r[1]),reverse=True) if 0<=now-stamp(at)<=7*86400]
 if not rules.get('enabled'):news=[u for u in news if u in rules['proof']]
 parents={u.rsplit('/',2)[0]+'/' for u in news};state=load_parents(folder,parents);side=load_parents(Path(folder)/'voe-state',parents)
 out={}
 for url in news:
  for ep in (state['episodes'].get(url),side['episodes'].get(url)):
   for p in (ep or {}).get('providers',[]):
    for link in p.get('links',[]):
     if target(p.get('family'),link,rules):out[sha((p['name']+'\0'+link).encode())]={'family':p['family'],'name':p['name'],'url':link,'episode':url}
   # «Descargar en MEGA» links are checked like options; otherwise only renewal would ever refresh them.
   for x in (ep or {}).get('downloads',[]):
    link,name=x.get('url',''),x.get('name','Mega')
    if x.get('family')=='mega' and target('mega',link,rules):out[sha((name+'\0'+link).encode())]={'family':'mega','name':name,'url':link,'episode':url,'download':True}
 # Links that two devices reported as not playing (help Worker), any age: checked first, judged as usual.
 reports=Path(folder)/'dead-reports.json'
 if rules.get('enabled') and reports.exists():
  for r in json.loads(reports.read_bytes()).get('links',[])[:300]:
   family,link,name=r.get('family'),str(r.get('url','')),str(r.get('name',''))
   if target(family,link,rules):out.setdefault(sha((name+'\0'+link).encode()),{'family':family,'name':name,'url':link,'episode':r.get('episode')})['reported']=True
 return out
def due(entry,now):
 if not entry or 'checkedAt' not in entry:return True
 kind='excluded' if entry.get('excluded') else entry.get('state','unknown')
 return now-entry['checkedAt']>=INTERVAL.get(kind,INTERVAL['unknown'])
def check(folder,now=None,limit=6,pause=2.5,fetcher=fetch,sleep=time.sleep,budget=75):
 """Check a few due links; deletion counts only when a fake id reads deleted and a real link reads alive."""
 folder=Path(folder);now=time.time() if now is None else now;rules=policy();started=time.time()
 path=folder/'link-health.json';health=json.loads(path.read_bytes()) if path.exists() else {'schema':1,'links':{},'controls':{},'canaries':{}}
 links=health['links'];found=candidates(folder,now,rules)
 def ready(k):
  entry=links.get(k)
  return due(entry,now) or (found[k].get('reported') and now-(entry or {}).get('checkedAt',0)>=REPORTED_RECHECK)
 ordered=sorted((k for k in found if ready(k)),key=lambda k:(k in links,links.get(k,{}).get('checkedAt',0)))
 queue=[k for k in ordered if found[k].get('reported')][:REPORTED_LIMIT]+[k for k in ordered if not found[k].get('reported')][:limit]
 families=sorted({found[k]['family'] for k in queue});results={};summary={'checked':0,'alive':0,'dead':0,'unknown':0,'suspended':[]};sent=[0]
 def get(url):
  # One request at a time with a fixed pause; no parallel servers, no retries inside a run.
  if sent[0]:sleep(pause)
  sent[0]+=1
  try:return fetcher(url)
  except Exception as error:return None,type(error).__name__
 for family in families:
  canary=health['canaries'].get(family,{})
  if now-canary.get('at',0)>=(6*3600 if canary.get('ok') else 3600):
   s,b=get(target(family,{'mp4upload':'https://www.mp4upload.com/embed-%s.html','streamwish':'https://hgcloud.to/e/%s','vidhide':'https://vidhidevip.com/embed/%s','voe':'https://voe.sx/e/%s','mega':'https://mega.nz/file/%s#'+'z'*43}[family]%(FAKE[:8] if family=='mega' else FAKE),rules))
   health['canaries'][family]=canary={'at':now,'ok':classify(family,s,b)=='dead','status':s}
 for key in queue:
  if time.time()-started>budget:break
  entry=links.get(key) or dict(found.get(key,{}))
  s,b=get(target(entry['family'],entry['url'],rules));results[key]=(classify(entry['family'],s,b),s);links[key]=entry
 alive={links[k]['family'] for k,(kind,_) in results.items() if kind=='alive'}
 for family in sorted({links[k]['family'] for k,(kind,_) in results.items() if kind=='dead'}-alive):
  # Positive control only when a deletion is about to count: last link seen alive, else the fixed policy sample.
  remembered=links.get(health['controls'].get(family),{}).get('url')
  for url in dict.fromkeys(u for u in (remembered,rules.get('controls',{}).get(family)) if u):
   if classify(family,*get(target(family,url,rules)))=='alive':alive.add(family);break
 for key,(kind,status) in results.items():
  entry=links[key];family=entry['family'];entry.update(checkedAt=now,status=status);summary['checked']+=1
  if kind=='dead' and not (health['canaries'][family]['ok'] and family in alive):
   # Uniform 404/block pages must never empty a provider: no live control in this run, no evidence.
   kind='unknown';entry['reason']='no-control';family in summary['suspended'] or summary['suspended'].append(family)
  else:entry.pop('reason',None)
  entry['state']=kind;summary[kind]+=1
  if kind=='alive':
   entry.update(deadChecks=[],excluded=False);health['controls'][family]=key
  elif kind=='dead':
   checks=(entry.get('deadChecks',[])+[now])[-3:];entry['deadChecks']=checks
   if not entry.get('excluded') and checks[-1]-checks[0]>=CONFIRM_GAP:entry.update(excluded=True,excludedAt=now)
 for key in list(links):
  if key not in found and now-links[key].get('checkedAt',now)>14*86400:links.pop(key)
 summary.update(excluded=sum(1 for e in links.values() if e.get('excluded')),tracked=len(links),candidates=len(found),checkedAt=now,playbackVerified=False,aiCalls=0)
 health['last']=summary;path.write_text(json.dumps(health,sort_keys=True,separators=(',',':')),encoding='utf-8')
 return summary
def excluded_keys(folder):
 """Keys of confirmed deleted files (options or MEGA downloads), same policy scope as exclude()."""
 path=Path(folder)/'link-health.json'
 if not path.exists():return set()
 rules=policy()
 return {k for k,e in json.loads(path.read_bytes())['links'].items() if e.get('excluded') and (rules.get('enabled') or e.get('episode') in rules['proof'])}
def exclude(folder,approved):
 """Withdraw confirmed deleted files from the signed channel; other options and records stay intact."""
 path=Path(folder)/'link-health.json'
 if not path.exists():return 0
 rules=policy();count=0
 for key,entry in json.loads(path.read_bytes())['links'].items():
  if entry.get('excluded') and approved.get(key) and (rules.get('enabled') or entry.get('episode') in rules['proof']):approved[key]=False;count+=1
 return count
