"""Hourly cloud job; real app validation before and after static-only publication."""
from pathlib import Path
import os,sys,json,gzip,hashlib,datetime,subprocess,tempfile,shutil,re,time
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from archive_state import load as load_observations,save as save_observations,merge as merge_observations
from no_redirect import NO_REDIRECT
W=Path(__file__).resolve().parent
D=Path(os.environ.get('ZZ_DATA',W/'state')).resolve()
BASE='https://zzanime-respaldo.zzcoredev.workers.dev'
COLLECTION_BATCHES=2
RETRY_SECONDS=15*60
# VOE-only news (≤7 days) are retried hourly, 4 per run: a source fix (e.g. AnimeFLV Mega) must reach new
# chapters within the hour, not after a 6 h backoff.
# Installed APKs reject the whole channel above these (ProviderBackupStore): keep a margin, never exceed.
APP_SERIES_LIMIT=5053
APP_INDEX_BYTES=2*1024*1024-262144
VOE_RECHECK_SECONDS=3600
VOE_RECHECK_LIMIT=4
REVIEW_FAMILIES=('mega','mixdrop')
PROOF_EPISODES=['https://jkanime.net/psyren/1/','https://jkanime.net/dark-summoner-to-dekiteiru/1/']
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def put(p,b):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
def record_recent(state,recent,instant):
 # Homepage presence is a real observation; refreshing old providers is not a release.
 seen=state.setdefault('newsSeen',{})
 for url in recent[:100]:
  if not isinstance(url,str) or not re.fullmatch(r'https://jkanime\.net/[a-zA-Z0-9_-]+/[1-9][0-9]*/',url):continue
  parent=url.rsplit('/',2)[0]+'/'
  if url in state['episodes'] and url in state['listings'].get(parent,{}).get('episodes',[]):seen.setdefault(url,instant.isoformat().replace('+00:00','Z'))
def voe_only_news(state,instant):
 # News seen in the last 7 days that have no root-channel record (only the VOE complement, or nothing).
 out=[]
 for url,seen in sorted(state.get('newsSeen',{}).items(),key=lambda row:str(row[1]),reverse=True):
  try:age=(instant-datetime.datetime.fromisoformat(seen.replace('Z','+00:00'))).total_seconds()
  except (ValueError,TypeError,AttributeError):continue
  if url not in state['episodes'] and 0<=age<=7*86400:out.append(url)
 return out
def command(args,**kw):return subprocess.run(args,check=True,capture_output=True,text=True,encoding='utf-8',**kw).stdout
def compile_java(runtime,modern=False):
 cp=os.pathsep.join(str(p) for p in (W/'lib').glob('*.jar'))
 command(['javac','-encoding','UTF-8','-cp',cp,'-d',str(runtime),*[str(p) for p in (W/('voe-java' if modern else 'java')).glob('*.java')],str(W/'CloudVerify.java'),*([str(W/'VoeOverlayAudit.java')] if modern else [])])
 return str(runtime)+os.pathsep+cp
def build(state,approved,now,allow_voe=False,plays=None,marks=None,dead=None,mega_alive=None):
 rows={}
 for url,ep in state['episodes'].items():
  parent=url.rsplit('/',2)[0]+'/'
  listing=state['listings'].get(parent)
  age=(now-datetime.datetime.fromisoformat(ep['observedAt'].replace('Z','+00:00'))).total_seconds()
  # Chapters never expire: they stay published with their real observation date; only links the
  # link checker confirms dead are excluded. Renewal keeps refreshing them, oldest first.
  if not listing or url not in listing['episodes'] or not ep.get('complete') or age<0:continue
  options=[];seen=set()
  # AnimeFLV lists MEGA and MixDrop under reviewProviders; both count once the real validator approves them
  # (MEGA also needs MEGA's API to read it alive). MixDrop from FLV approved by Robin 31/10/2026.
  review=[dict(p,review=True) for p in ep.get('reviewProviders',[]) if p.get('family') in REVIEW_FAMILIES]
  for provider in ep['providers']+review:
   if provider.get('family')=='voe' and not allow_voe:continue
   if ep.get('sourceSeries','').startswith('https://vww.animeflv.one/') and provider.get('family') not in ['mp4upload','streamwish','vidhide','mega','mixdrop','filemoon',*(['voe'] if allow_voe else [])]:continue
   for link in provider.get('links',[]):
    k=sha((provider['name']+'\0'+link).encode())
    # MEGA from TioAnime or from AnimeFLV's review list counts only once MEGA's API read it alive.
    if provider.get('family')=='mega' and (provider.get('review') or ep.get('sourceSeries','').startswith('https://tioanime.com/')) and k not in (mega_alive or ()):continue
    if not approved.get(k) or k in seen:continue
    seen.add(k);options.append({'family':provider['family'],'name':provider['name'],'url':link})
  downloads=[x for x in ep.get('downloads',[]) if x.get('name')=='Mega' and x.get('family')=='mega' and re.fullmatch(r'https://(?:www\.)?mega\.nz/(?:#![A-Za-z0-9_-]{8}![A-Za-z0-9_-]{43}|file/[A-Za-z0-9_-]{8}#[A-Za-z0-9_-]{43})',x.get('url','')) and sha((x['name']+'\0'+x['url']).encode()) not in (dead or ())][:8]
  # Extra families for móvil 92+/TV 116+, only next to at least one regular option (older apps drop empty options).
  import extra_options
  extra=extra_options.build(ep,dead or set(),seen,sha) if options else []
  if options:rows.setdefault(parent,[]).append({'url':url,'observedAt':ep['observedAt'],'playbackVerified':False,'options':options,**({'extraOptions':extra} if extra else {}),**({'downloads':downloads} if downloads else {}),**{k:ep[k] for k in ['sourceEpisode','sourceSeries'] if k in ep}})
 recency={parent:max(e['observedAt'] for e in eps) for parent,eps in rows.items()}
 if len(rows)>APP_SERIES_LIMIT:
  # Chapters never expire, so the series count only grows: drop the least recently observed, never the channel.
  rows={parent:rows[parent] for parent in sorted(rows,key=lambda p:recency[p],reverse=True)[:APP_SERIES_LIMIT]}
 available={ep['url'] for eps in rows.values() for ep in eps};news=[]
 for url,observed in sorted(state.get('newsSeen',{}).items(),key=lambda item:item[1],reverse=True):
  try:age=(now-datetime.datetime.fromisoformat(observed.replace('Z','+00:00'))).total_seconds()
  except (ValueError,TypeError):continue
  if url in available and 0<=age<=7*86400:news.append({'url':url,'number':int(url.rstrip('/').rsplit('/',1)[1]),'firstSeenAt':observed})
  if len(news)>=100:break
 index={'schema':1,'createdAt':now.isoformat().replace('+00:00','Z'),'playbackVerified':False,'series':{},'feed':{'schema':1,'episodes':news}};files={}
 for parent,eps in sorted(rows.items()):
  listing=state['listings'][parent]
  row={'schema':1,'series':parent,'listedAt':listing['observedAt'],'listedEpisodes':listing['episodes'],'episodes':sorted(eps,key=lambda e:e['url']),'playbackVerified':False,**{k:listing[k] for k in ['sourceSeries','identityEvidence'] if k in listing}}
  body=raw(row);packed=gzip.compress(body,mtime=0);h=sha(packed);name='series/'+h+'.bin'
  if max(len(body),len(packed))>2097152:raise ValueError('App shard limit')
  files[name]=packed;index['series'][sha(parent.encode())]={'path':name,'sha256':h,'bytes':len(packed),'expandedBytes':len(body),'episodes':len(eps)}
 # 10/11 (app 180): episode lists WITHOUT links, free to read when a ficha opens (channel_gate.mjs only counts series/).
 # 256 buckets by the first two hex digits of the series key keep the file count low; the app reads index['lists'].
 buckets={}
 for parent,eps in rows.items():
  listing=state['listings'][parent]
  buckets.setdefault(sha(parent.encode())[:2],{})[sha(parent.encode())]={'series':parent,'listedAt':listing['observedAt'],'listedEpisodes':listing['episodes'],'episodes':[{'url':e['url'],'observedAt':e['observedAt'],'families':sorted({o['family'] for o in e['options']})} for e in sorted(eps,key=lambda e:e['url'])]}
 index['lists']={}
 for bucket,series in sorted(buckets.items()):
  body=raw({'schema':1,'series':series});packed=gzip.compress(body,mtime=0);h=sha(packed);name='lista/'+h+'.bin'
  files[name]=packed;index['lists'][bucket]={'path':name,'sha256':h,'bytes':len(packed)}
 if not rows:raise ValueError('No approved observations; previous channel retained')
 import schedule,help_chain
 titles=help_chain.titles();index['schedule']=schedule.build(state,available,now,titles)
 # S2: device summaries only count when attested (network-v2) and fresh for this run's clock; otherwise they are left out.
 import signal_policy
 if plays and signal_policy.fresh(plays,now):
  import plays as play_votes
  ranking,scores=play_votes.ranking(plays,set(rows),titles),play_votes.scores(plays)
  if ranking is not None:index['ranking']=ranking
  if scores is not None:index['playScores']=scores
 if marks and signal_policy.fresh(marks,now):
  import skip_marks
  built=skip_marks.build(marks,available)
  if built is not None:index['skipMarks']=built
 while len(raw(index))>APP_INDEX_BYTES:
  # Over the app limit: intro marks and option scores go first, then the least recently observed series.
  if index.pop('skipMarks',None) is not None or index.pop('playScores',None) is not None:continue
  if len(index['series'])<=1:break
  oldest=min(rows,key=lambda p:recency[p]);entry=index['series'].pop(sha(oldest.encode()));files.pop(entry['path'],None);rows.pop(oldest)
 return index,files
def main():
 D.mkdir(parents=True,exist_ok=True);proof=os.environ.get('ZZ_PROOF')=='true'
 if proof and '--publish' in sys.argv:raise ValueError('La prueba no puede publicar en producción (auditoría S-01)')
 collected=0;recent_added=0;links_changed=0
 if '--collect' in sys.argv:
  # Collection failure keeps already observed valid data; retry on the next hourly invocation.
  if os.environ.get('ZZ_COLLECTOR_URL'):
   import urllib.request,new_series
   state=load_observations(D)
   incidents_path=D/'news-incidents.json';incidents=json.loads(incidents_path.read_bytes()) if incidents_path.exists() else {};primary='not-checked'
   instant=datetime.datetime.now(datetime.timezone.utc)
   put(D/'collection-status.json',raw({'state':'checking','lastAttempt':instant.isoformat().replace('+00:00','Z'),'retryMinutes':RETRY_SECONDS//60}))
   for attempt in range(1 if proof else COLLECTION_BATCHES):
    recent=sorted(state['episodes'].items(),key=lambda row:state.get('newsSeen',{}).get(row[0],''),reverse=True)
    skip=[url for url,ep in recent if (instant-datetime.datetime.fromisoformat(ep['observedAt'].replace('Z','+00:00'))).total_seconds()<6*86400 and not (ep.get('sourceSeries','').startswith('https://tioanime.com/') and all(p.get('family')=='mega' for p in ep.get('providers',[])))][:2500]
    from voe_channel import fresh_urls,split
    from extra_channel import split as split_extra
    # News seen in the last 7 days without a root-channel record (VOE-only) are rechecked through the
    # source chain with a backoff; historical VOE-only episodes are left to the renewal job.
    voe_fresh=fresh_urls(D,instant.timestamp());recheck=state.setdefault('voeRecheck',{});voe_news=voe_only_news(state,instant)
    for url in list(recheck):
     if url not in voe_news:recheck.pop(url)
    due=[url for url in voe_news if instant.timestamp()-recheck.get(url,0)>=VOE_RECHECK_SECONDS][:VOE_RECHECK_LIMIT]
    skip=skip[:2000]+[url for url in voe_fresh if url not in due]
    deferred=state.setdefault('deferred',{});skip+=list(url for url,stamp in deferred.items() if instant.timestamp()-stamp<RETRY_SECONDS and url not in skip);retry=[url for url in state.get('pending',[]) if url not in skip][:200]
    retry=(retry+[url for url in due if url not in retry and url not in skip])[:200]
    for url in due:recheck[url]=instant.timestamp()
    # 12/11: the proof always asks for chapter 1 of its two series too, so it does not depend on their latest chapter
    # being on the home pages that day (JK's home may be unreachable from the cloud and the backups list only some).
    if proof:retry=PROOF_EPISODES
    req=urllib.request.Request(os.environ['ZZ_COLLECTOR_URL'],data=raw({'skip':skip[-2500:],'retry':retry,'proof':proof,'checkPrimary':attempt==0,**({} if proof else {'newSeries':new_series.rows(D)})}),headers={'Authorization':'Bearer '+os.environ['ZZ_COLLECTOR_KEY'],'Content-Type':'application/json','User-Agent':'ZZAnime-Data/1'},method='POST')
    with NO_REDIRECT.open(req,timeout=60) as response:result=json.loads(response.read(2097153))
    if not result.get('passed'):raise ValueError('Cloud source unavailable; previous data retained')
    # Series the collector could not place: verified on TioAnime/AnimeFLV and sent with the next request.
    if not proof:state['pending']=sorted(set(state.get('pending',[]))|set(new_series.verify(D,result.get('unknownSeries',[]),json.loads((Path(__file__).with_name('catalogue.json')).read_bytes()))))
    received=set(result['state']['episodes']);extra_in,extra_captured=split_extra(D,result['state']);incoming,voe_captured=split(D,extra_in);voe_captured+=extra_captured;collected+=len(incoming['episodes'])+voe_captured;newly_deferred=[url for url in incoming.get('pending',[]) if url not in skip]
    if result.get('primary')!='not-checked':primary=result.get('primary','unknown')
    for url,error in result.get('errors',{}).items():incidents[url]={'lastAttempt':instant.isoformat().replace('+00:00','Z'),'error':error,'sources':result.get('diagnostics',{}).get(url,{}),'retryMinutes':RETRY_SECONDS//60}
    for url in received:incidents.pop(url,None)
    put(incidents_path,raw(incidents))
    for url in newly_deferred:deferred[url]=instant.timestamp()
    for url,ep in result['state']['episodes'].items():state.setdefault('newsSeen',{}).setdefault(url,ep['observedAt'])
    merge_observations(state,incoming);before_seen=len(state.get('newsSeen',{}));record_recent(state,result.get('recent',[]),instant);recent_added+=len(state.get('newsSeen',{}))-before_seen;state['pending']=sorted((set(state.get('pending',[]))|set(incoming.get('pending',[])))-received);save_observations(D,state,set(incoming['listings']));put(D/'collection-status.json',raw({'state':'complete','coverage':'partial' if incidents else 'collected-candidates','checkedAt':instant.isoformat().replace('+00:00','Z'),'primary':primary,'held':result.get('held',0),'pending':len(state['pending']),'incidents':len(incidents),'collected':collected,'batch':attempt+1,'retryMinutes':RETRY_SECONDS//60,'voeOnly':len(voe_only_news(state,instant)),'voeRecheckPending':len(state.get('voeRecheck',{}))}))
    if not incoming['episodes'] and not newly_deferred:break
   if os.environ.get('ZZ_HELP_URL') and not proof:
    # Device help only fills chapters the cloud asked for; a failing help service never blocks collection.
    try:
     import help_chain;collected+=help_chain.pull(D,state,instant)['imported']
    except Exception as error:print(json.dumps({'helpChainError':type(error).__name__+': '+str(error)[:120]}))
   if '--publish' in sys.argv and not proof:
    # A few provider pages per run; a failing check never blocks the channel and never claims playback.
    try:
     from link_health import check as check_links
     before=json.loads((D/'link-health.json').read_bytes()).get('last',{}).get('excluded',0) if (D/'link-health.json').exists() else 0;links=check_links(D);links_changed=links['excluded']!=before
    except Exception as error:print(json.dumps({'linkHealthError':type(error).__name__+': '+str(error)[:120]}))
  else:subprocess.run(['node',str(W/'collect.cjs')],env=dict(os.environ,ZZ_DATA=str(D)),check=False,timeout=420)
  # Historical changes remain for renewal's final publish; an empty news check must not redeploy them.
  if '--news-only' in sys.argv and os.environ.get('ZZ_COLLECTOR_URL') and not proof and collected==0 and recent_added==0 and not links_changed:
   print(json.dumps({'newsUnchanged':True,'historicalPublicationDeferred':True,'aiCalls':0}));return
 state=load_observations(D);now=datetime.datetime.now(datetime.timezone.utc)
 # Undo the obsolete homepage baseline only; preserve collected options and true news observations.
 seed_path=W/'recent-seed.json'
 if seed_path.exists():
  seed_body=seed_path.read_bytes();seed_hash=sha(seed_body)
  if state.get('recentSeedHash')==seed_hash:
   seed=json.loads(seed_body);observed=datetime.datetime.fromisoformat(seed['observedAt'].replace('Z','+00:00')).isoformat().replace('+00:00','Z')
   for url in seed['recent']:
    if state.get('newsSeen',{}).get(url)==observed:state['newsSeen'].pop(url)
   state['recentSeedHash']='removed';save_observations(D,state,set())
 with tempfile.TemporaryDirectory() as tmp:
  tmp=Path(tmp);cp=compile_java(tmp/'classes');queries={}
  for ep in state['episodes'].values():
   for p in ep.get('providers',[])+[q for q in ep.get('reviewProviders',[]) if q.get('family') in REVIEW_FAMILIES]:
    for url in p.get('links',[]):queries[sha((p['name']+'\0'+url).encode())]={'name':p['name'],'url':url}
  output=command(['java','-cp',cp,'tv.jkanime.web.RuntimeOptionAudit'],input='\n'.join(json.dumps(v) for v in queries.values()))
  approved={r['key']:r['approved'] for r in map(json.loads,output.splitlines())}
  if set(approved)!=set(queries):raise ValueError('Incomplete real app option validation')
  from link_health import exclude
  exclude(D,approved)
  import plays as play_votes
  import skip_marks
  from link_health import excluded_keys
  import mega_check
  if '--publish' in sys.argv and not proof:
   try:print(json.dumps({'megaCheck':mega_check.check(D,state)}))
   except Exception as error:print(json.dumps({'megaCheckError':type(error).__name__+': '+str(error)[:120]}))
  index,files=build(state,approved,now,plays=play_votes.load(D,now=now),marks=skip_marks.load(D,now=now),dead=excluded_keys(D),mega_alive=mega_check.alive(D))
  _res=locals().get('result') or {}
  if proof and (len(index['series'])!=2 or sum(x['episodes'] for x in index['series'].values())<2):raise ValueError('Two-series proof incomplete; do not activate: '+json.dumps({'index':{k:v.get('episodes') for k,v in index['series'].items()},'collected':{u.split('/')[-3]+'/'+u.split('/')[-2]:sorted({str(p.get('name'))+('' if approved.get(sha((p['name']+chr(0)+l).encode())) else ':no') for p in e.get('providers',[]) for l in p.get('links',[])}) for u,e in state['episodes'].items()},'source':{k:_res.get(k) for k in ('held','primary','requests','cacheHits')},'errors':{k:str(v)[:160] for k,v in (_res.get('errors') or {}).items() if 'psyren' in k or 'dark-summoner' in k},'diagnostics':{k:json.dumps(v)[:300] for k,v in (_res.get('diagnostics') or {}).items() if 'psyren' in k or 'dark-summoner' in k}},ensure_ascii=False))  # sin enlaces (registro público)
  public=(W/'public-key.der').read_bytes()
  private=os.environ.get('ZZ_SIGNING_KEY','')
  key=serialization.load_pem_private_key(private.encode(),None) if private else None
  if key and key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)!=public:raise ValueError('Installed app key differs')
  if not key:
   if '--publish' in sys.argv:raise ValueError('Cloud signing secret missing')
   key=rsa.generate_private_key(public_exponent=65537,key_size=2048);public=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
  site=tmp/'site';assets=site/'assets'
  digest=sha(raw(index));name='indexes/'+digest+'.bin';files[name]=raw(index)
  import help_chain
  try:wanted=None if proof else help_chain.wanted(state,files,now,help_chain.policy())
  except Exception as error:wanted=None;print(json.dumps({'helpWantedError':type(error).__name__+': '+str(error)[:120]}))
  # Extra signed field: installed readers check only their own keys, so older APKs ignore it.
  import remote_config
  try:
   config=None if proof else remote_config.load(now)
   # Server status from the daily playback probe (branch playback-probe, copied to $RUNNER_TEMP by the workflow).
   try:health=None if proof or config is None else remote_config.provider_health(now)
   except Exception as error:health=None;print(json.dumps({'providerHealthError':type(error).__name__+': '+str(error)[:120]}))
   if health:config['providerHealth']=health
  except Exception as error:config=None;print(json.dumps({'remoteConfigError':type(error).__name__+': '+str(error)[:120]}))
  payload=raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':now.isoformat().replace('+00:00','Z'),'indexSha256':digest,'indexPath':name,'indexBytes':len(files[name]),'mode':'daily-new',**({'wanted':wanted} if wanted is not None else {}),**({'config':config} if config else {})})
  files['channel.json']=raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})
  from voe_channel import render
  extra_files,voe_cp,voe_digest=render(D,now,key,tmp)
  files.update(extra_files)
  # /extra/: chapters whose only servers are new families, read by móvil 93+/TV 117+ only.
  import extra_channel
  try:extra_only={} if proof else extra_channel.render(D,now,key,excluded_keys(D))
  except Exception as error:extra_only={};print(json.dumps({'extraChannelError':type(error).__name__+': '+str(error)[:120]}))
  files.update(extra_only);extra_digest=next((n for n in extra_only if n.startswith('extra/indexes/')),None)
  files['_headers']=b'/channel.json\n  Cache-Control: public, max-age=300, must-revalidate\n/voe/channel.json\n  Cache-Control: public, max-age=300, must-revalidate\n/extra/channel.json\n  Cache-Control: public, max-age=300, must-revalidate\n/indexes/*\n  Cache-Control: public, max-age=31536000, immutable\n/series/*\n  Cache-Control: public, max-age=31536000, immutable\n/lista/*\n  Cache-Control: public, max-age=31536000, immutable\n'
  files['robots.txt']=b'# ZZAnime: canal privado de la app. No se permite indexar, recopilar en masa ni entrenar IA.\nUser-agent: *\nContent-Signal: search=no, ai-train=no, ai-input=no\nDisallow: /\n'
  files['index.html']=b'<!doctype html><meta charset="utf-8"><title>ZZAnime</title><p>Canal de datos de ZZAnime.</p>'
  for n,b in files.items():put(assets/n,b)
  put(tmp/'key.der',public)
  proof_result=json.loads(command(['java','-cp',cp,'tv.jkanime.web.CloudVerify',str(assets),str(tmp/'key.der'),str(tmp/'cache')]))
  voe_proof=json.loads(command(['java','-cp',voe_cp,'tv.jkanime.web.CloudVerify',str(assets/'voe'),str(tmp/'key.der'),str(tmp/'voe-cache')])) if voe_cp else None
  content=sha(raw({'series':index['series'],'feed':index['feed'],'voe':voe_digest,**({'extra':extra_digest} if extra_digest else {}),**({'wanted':[w['url'] for w in wanted]} if wanted else {}),**({'config':config} if config else {})}));prior=json.loads((D/'publication.json').read_bytes()) if (D/'publication.json').exists() else {}
  changed=prior.get('contentSha256')!=content or (now-datetime.datetime.fromisoformat(prior.get('publishedAt','2000-01-01T00:00:00+00:00'))).total_seconds()>86400
  report={**proof_result,'checkedAt':now.isoformat(),'proof':proof,'published':False,'changed':changed,'contentSha256':content,'aiCalls':0,'pcRequired':False,'voe':voe_proof}
  if '--publish' in sys.argv and changed:
   if not os.environ.get('CLOUDFLARE_API_TOKEN') and not (proof and '--local-proof-publication' in sys.argv):raise ValueError('Cloudflare publication secret missing')
   # Keep exactly one prior immutable generation; never publish arbitrary state/private files.
   old=D/'published-assets'
   if old.exists():
    import re
    for p in old.rglob('*.bin'):
     n=p.relative_to(old).as_posix()
     if re.fullmatch(r'(?:voe/|extra/)?(series|indexes|lista)/[a-f0-9]{64}\.bin',n) and n not in files:put(assets/n,p.read_bytes())
   # 9/11: owner-only editor view (dead links, help status) under /owner/, never in the public GitHub repo (owner_files.py, channel_gate.mjs).
   try:
    import owner_files
    for n,b in owner_files.build(D).items():put(assets/n,b)
   except Exception as error:print(json.dumps({'ownerFilesError':type(error).__name__+': '+str(error)[:120]}))
   if len(list(assets.rglob('*')))>18000 or any(p.stat().st_size>2097152 for p in assets.rglob('*') if p.is_file()):raise ValueError('Static/app limits; paid upgrade forbidden')
   # 169: channel_gate.mjs keeps channel.json public and asks a session (or the cloud key) for the link files once
   # ZZ_CHANNEL_REQUIRE is "true"; until then it only checks. ZZ_CHANNEL_KEY is a GitHub secret, never printed.
   shutil.copyfile(W/'channel_gate.mjs',site/'channel_gate.mjs');shutil.copyfile(W/'quota.mjs',site/'quota.mjs')
   if os.environ.get('ZZ_CHANNEL_REQUIRE','true')!='true':raise ValueError('ZZ_CHANNEL_REQUIRE must be "true": the channel never opens without session (auditoría A-03)')
   config={'name':'zzanime-respaldo','routes':[{'pattern':'respaldo.zzanime.uk','custom_domain':True}],'workers_dev':True,'account_id':'3407d07c06229321d34863cf0fdac02d','compatibility_date':'2026-10-26','main':'channel_gate.mjs','assets':{'directory':'./assets','binding':'ASSETS','run_worker_first':True,'not_found_handling':'none'},'vars':{'REQUIRE_SESSION':os.environ.get('ZZ_CHANNEL_REQUIRE','true'),'QUOTA_MODE':os.environ.get('ZZ_QUOTA_MODE') or 'count','QUOTA_DAY':os.environ.get('ZZ_QUOTA_DAY') or '300','LINK_RULES':os.environ.get('ZZ_LINK_RULES') or 'off'},'durable_objects':{'bindings':[{'name':'QUOTA','class_name':'Quota'}]},'migrations':[{'tag':'quota-v1','new_sqlite_classes':['Quota']}],'ratelimits':[{'name':'CHANNEL_LIMIT','namespace_id':'1170','simple':{'limit':60,'period':60}}],'send_metrics':False,'observability':{'enabled':False}}
   put(site/'wrangler.json',raw(config));cli=W/'node_modules/wrangler/bin/wrangler.js'
   # 9/11: the cloud key is a Cloudflare SECRET (not a plain variable visible in the dashboard); file outside site/, never published.
   secrets=[]
   if os.environ.get('ZZ_CHANNEL_KEY'):put(tmp/'channel-secrets.json',raw({'CLOUD_KEY':os.environ['ZZ_CHANNEL_KEY']}));secrets=['--secrets-file',str(tmp/'channel-secrets.json')]
   command(['node',str(cli),'deploy','--config',str(site/'wrangler.json'),*secrets],env=dict(os.environ,WRANGLER_SEND_METRICS='false'))
   for verification_attempt in range(13):
    try:
     remote=json.loads(command(['java','-cp',cp,'tv.jkanime.web.CloudVerify',str(assets),str(tmp/'key.der'),str(tmp/('remote-cache-'+str(verification_attempt))),BASE,str(old)]))
     if remote!=proof_result:raise ValueError('Remote app result differs')
     if voe_cp:
      remote_voe=json.loads(command(['java','-cp',voe_cp,'tv.jkanime.web.CloudVerify',str(assets/'voe'),str(tmp/'key.der'),str(tmp/('voe-remote-'+str(verification_attempt))),BASE+'/voe',str(old/'voe')]))
      if remote_voe!=voe_proof:raise ValueError('Remote VOE reader differs')
     break
    except (subprocess.CalledProcessError,ValueError) as error:
     # 9/11: show why the remote check failed (Java message only; no keys are ever in it).
     print(json.dumps({'remoteVerify':verification_attempt,'error':str(getattr(error,'stderr','') or error)[-500:]}),flush=True)
     if verification_attempt==12:raise
     time.sleep(25)
   # Retain only current generation in state. The next deployment adds it as its prior generation.
   if old.exists():shutil.rmtree(old)
   for n,b in files.items():put(old/n,b)
   report.update(published=True,verifiedRemote=True,publishedAt=now.isoformat());put(D/'publication.json',raw(report))
   help_chain.record_published(D,wanted,now)
  put(D/'verification.json',raw(report));print(json.dumps(report))
if __name__=='__main__':main()
