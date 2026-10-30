"""Help chain (task 10): the cloud asks for what it lacks; devices answer only that.

The signed channel carries a short "wanted" list: new chapters without options and, in open mode,
the stored chapters with the oldest observation ("renew"). The help Worker accepts submissions only
for wanted chapters, requires two devices on two different networks plus a content check, and this
module imports only what the cloud itself asked for in its last published channel."""
from pathlib import Path
import datetime,gzip,hashlib,hmac,json,os,re,urllib.request
from archive_state import save as save_observations,stamp
W=Path(__file__).resolve().parent
EPISODE=re.compile(r'https://jkanime\.net/[a-zA-Z0-9_-]+/[1-9][0-9]*/')
# Same families as the app's ProviderPlaybackPolicy.family; VOE-only chapters are exactly what is wanted.
FAMILIES={'desu','magi','mega','streamwish','vidhide','mixdrop','mp4upload','streamtape'}
CHECKS={'name-match','quorum3'}
MAX_WANTED=40
MAX_RENEW=180
RENEW_AFTER=4*86400
# Installed APKs read channel.json with a 64 KB limit; the wanted list stays far below it.
WANTED_BYTES=24000
MAX_IMPORT=400
HELP_URL='https://zzanime-ayuda.zzcoredev.workers.dev'
def iso(t):return t.isoformat().replace('+00:00','Z')
def derived(label,secret=None):
 # Help Worker secrets derive from the existing collector secret, so no new GitHub secret is needed.
 secret=os.environ.get('ZZ_COLLECTOR_KEY','') if secret is None else secret
 return hmac.new(secret.encode(),('zzanime-ayuda/'+label).encode(),hashlib.sha256).hexdigest() if secret else ''
def policy(path=None):
 path=path or W/'help-policy.json';x=json.loads(path.read_bytes()) if path.exists() else {}
 mode=x.get('mode','off');trial=[u for u in x.get('trial',[]) if isinstance(u,str) and EPISODE.fullmatch(u)]
 if mode not in ('off','trial','open'):raise ValueError('Help policy mode')
 if mode=='trial' and len(set(trial))!=2:raise ValueError('Help trial needs exactly two chapters')
 return {'mode':mode,'trial':trial,'max':max(0,min(int(x.get('maxWanted',MAX_WANTED)),MAX_WANTED)),'renew':max(0,min(int(x.get('maxRenew',MAX_RENEW)),MAX_RENEW))}
def available(files):
 return {ep['url'] for n,b in files.items() if n.startswith('series/') for ep in json.loads(gzip.decompress(b))['episodes']}
def titles():
 return {r['url']:r.get('title','') for r in json.loads((W/'catalogue.json').read_bytes())}
def wanted(state,files,now,rules,catalogue=None):
 # New chapters first (no root-channel option, no stored record); they drop out once they have options.
 if rules['mode']=='off':return None
 have=available(files);catalogue=titles() if catalogue is None else catalogue;rows={}
 def open_(url):
  ep=state['episodes'].get(url);return EPISODE.fullmatch(url) and url not in have and (ep is None or not ep.get('providers'))
 for url,seen in state.get('newsSeen',{}).items():
  try:age=(now-datetime.datetime.fromisoformat(str(seen).replace('Z','+00:00'))).total_seconds()
  except ValueError:continue
  if 0<=age<=7*86400 and open_(url):rows[url]=seen
 for url in state.get('pending',[]):
  if isinstance(url,str) and open_(url):rows.setdefault(url,None)
 if rules['mode']=='trial':rows={u:s for u,s in rows.items() if u in rules['trial']}
 def entry(url,**extra):return {'url':url,'number':int(url.rstrip('/').rsplit('/',1)[1]),'title':catalogue.get(url.rsplit('/',2)[0]+'/',''),**extra}
 out=[entry(url,**({'firstSeenAt':seen} if seen else {})) for url,seen in sorted(rows.items(),key=lambda r:(r[1] is not None,str(r[1])),reverse=True)[:rules['max']]]
 # Renewal (open mode): published chapters with the oldest real observation are re-read by devices.
 if rules['mode']=='open' and rules.get('renew'):
  old=sorted((stamp(ep.get('observedAt')),url) for url,ep in state['episodes'].items() if url in have and url not in rows and EPISODE.fullmatch(url) and now.timestamp()-stamp(ep.get('observedAt'))>=RENEW_AFTER)
  for _,url in old[:rules['renew']]:out.append(entry(url,renew=True))
 while out and len(json.dumps(out,ensure_ascii=False,separators=(',',':')).encode())>WANTED_BYTES:out.pop()
 return out
def record_published(folder,wanted_rows,now):
 rows=wanted_rows or []
 (folder/'help-wanted.json').write_bytes(json.dumps({'publishedAt':iso(now),'urls':[w['url'] for w in rows],'renew':[w['url'] for w in rows if w.get('renew')]},sort_keys=True).encode())
def accept(data,state,asked,now,renew=frozenset()):
 # Only chapters this cloud published as wanted. A stored record is replaced only when the cloud asked
 # to renew it and the devices' observation is newer; otherwise records and dates are never touched.
 if data.get('schema')!=1 or not isinstance(data.get('episodes'),list):raise ValueError('Help answer schema')
 incoming={'episodes':{},'listings':{}};seen={};held={}
 for row in data['episodes'][:MAX_IMPORT]:
  url=row.get('url') if isinstance(row,dict) else None
  if not isinstance(url,str) or not EPISODE.fullmatch(url) or url not in asked:held[str(url)[:200]]='Not asked by the cloud';continue
  try:at=datetime.datetime.fromisoformat(row['acceptedAt'].replace('Z','+00:00'))
  except (KeyError,TypeError,ValueError,AttributeError):held[url]='Invalid acceptance date';continue
  if not 0<=(now-at).total_seconds()<=7*86400:held[url]='Stale or future acceptance';continue
  old=state['episodes'].get(url)
  if old is not None and old.get('providers'):
   if url not in renew:held[url]='Already stored';continue
   if stamp(old.get('observedAt'))>=at.timestamp():held[url]='Stored observation is newer';continue
  providers={}
  for o in row.get('options',[])[:12]:
   if not isinstance(o,dict):continue
   name,family,link=o.get('name'),o.get('family'),o.get('url')
   if family not in FAMILIES or not isinstance(name,str) or not 0<len(name)<=70 or not isinstance(link,str) or not link.startswith('https://') or len(link)>500:continue
   if not (int(o.get('devices',0))>=2 and int(o.get('asns',0))>=2 and o.get('check') in CHECKS and (o['check']!='quorum3' or int(o['asns'])>=3)):continue
   p=providers.setdefault(name,{'name':name,'family':family,'links':[]})
   if p['family']==family and link not in p['links']:p['links'].append(link)
  if not providers:held[url]='No option passed the help checks';continue
  parent=url.rsplit('/',2)[0]+'/';listing=state['listings'].get(parent)
  incoming['episodes'][url]={'archiveVersion':3,'episode':url,'observedAt':iso(at),'complete':True,'providers':list(providers.values()),'helpEvidence':{'acceptedAt':iso(at),'source':'help-chain','renewed':url in renew}}
  # Keep the observed listing and its date; only a chapter without any listing gets a minimal one.
  incoming['listings'][parent]={**listing,'episodes':[url]} if listing else {'observedAt':iso(at),'complete':False,'helpListing':True,'episodes':[url]}
  if url not in renew:seen[url]=row.get('firstSeenAt') or iso(at)
 return incoming,seen,held
def pull(folder,state,now,fetch=None):
 base,key=os.environ.get('ZZ_HELP_URL'),os.environ.get('ZZ_HELP_KEY') or derived('help-key')
 if not base or not key:return {'state':'disabled','imported':0}
 path=folder/'help-wanted.json';published=json.loads(path.read_bytes()) if path.exists() else {}
 asked=set(published.get('urls',[]));renew=frozenset(published.get('renew',[]))&asked
 if not asked:return {'state':'nothing-asked','imported':0}
 if fetch is None:
  req=urllib.request.Request(base.rstrip('/')+'/v1/accepted',headers={'Authorization':'Bearer '+key,'User-Agent':'ZZAnime-Data/1'})
  with urllib.request.urlopen(req,timeout=60) as response:data=json.loads(response.read(4194305))
 else:data=fetch()
 incoming,seen,held=accept(data,state,asked,now,renew)
 for url,ep in incoming['episodes'].items():
  parent=url.rsplit('/',2)[0]+'/';old=state['listings'].get(parent)
  state['episodes'][url]=ep
  state['listings'][parent]={**old,'episodes':sorted(set(old['episodes'])|{url})} if old else incoming['listings'][parent]
  # Renewed chapters are not news; only new chapters enter the "Últimos episodios" feed.
  if url in seen:state.setdefault('newsSeen',{}).setdefault(url,seen[url])
 state['pending']=sorted(set(state.get('pending',[]))-set(incoming['episodes']))
 if incoming['episodes']:save_observations(folder,state,set(incoming['listings']))
 renewed=sum(1 for url in incoming['episodes'] if url in renew)
 report={'state':'imported' if incoming['episodes'] else 'unchanged','checkedAt':iso(now),'imported':len(incoming['episodes']),'renewed':renewed,'held':held,'asked':len(asked),'askedRenew':len(renew)}
 (folder/'help-status.json').write_bytes(json.dumps(report,sort_keys=True).encode());return report
