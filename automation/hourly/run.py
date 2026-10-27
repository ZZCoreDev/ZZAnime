"""Hourly cloud job; real app validation before and after static-only publication."""
from pathlib import Path
import os,sys,json,gzip,hashlib,datetime,subprocess,tempfile,shutil
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding,rsa
W=Path(__file__).resolve().parent
D=Path(os.environ.get('ZZ_DATA',W/'state')).resolve()
BASE='https://zzanime-respaldo.zzcoredev.workers.dev'
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def put(p,b):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
def command(args,**kw):return subprocess.run(args,check=True,capture_output=True,text=True,encoding='utf-8',**kw).stdout
def compile_java(runtime):
 cp=os.pathsep.join(str(p) for p in (W/'lib').glob('*.jar'))
 command(['javac','-encoding','UTF-8','-cp',cp,'-d',str(runtime),*[str(p) for p in (W/'java').glob('*.java')],str(W/'CloudVerify.java')])
 return str(runtime)+os.pathsep+cp
def build(state,approved,now):
 rows={}
 for url,ep in state['episodes'].items():
  parent=url.rsplit('/',2)[0]+'/'
  listing=state['listings'].get(parent)
  age=(now-datetime.datetime.fromisoformat(ep['observedAt'].replace('Z','+00:00'))).total_seconds()
  if not listing or url not in listing['episodes'] or not ep.get('complete') or not 0<=age<=7*86400:continue
  options=[];seen=set()
  for provider in ep['providers']:
   for link in provider.get('links',[]):
    k=sha((provider['name']+'\0'+link).encode())
    if not approved.get(k) or k in seen:continue
    seen.add(k);options.append({'family':provider['family'],'name':provider['name'],'url':link})
  if options:rows.setdefault(parent,[]).append({'url':url,'observedAt':ep['observedAt'],'playbackVerified':False,'options':options,**{k:ep[k] for k in ['sourceEpisode','sourceSeries'] if k in ep}})
 index={'schema':1,'createdAt':now.isoformat().replace('+00:00','Z'),'playbackVerified':False,'series':{}};files={}
 for parent,eps in sorted(rows.items()):
  listing=state['listings'][parent]
  row={'schema':1,'series':parent,'listedAt':listing['observedAt'],'listedEpisodes':listing['episodes'],'episodes':sorted(eps,key=lambda e:e['url']),'playbackVerified':False,**{k:listing[k] for k in ['sourceSeries','identityEvidence'] if k in listing}}
  body=raw(row);packed=gzip.compress(body,mtime=0);h=sha(packed);name='series/'+h+'.bin'
  if max(len(body),len(packed))>2097152:raise ValueError('App shard limit')
  files[name]=packed;index['series'][sha(parent.encode())]={'path':name,'sha256':h,'bytes':len(packed),'expandedBytes':len(body),'episodes':len(eps)}
 if not rows:raise ValueError('No approved observations; previous channel retained')
 return index,files
def main():
 D.mkdir(parents=True,exist_ok=True);proof=os.environ.get('ZZ_PROOF')=='true'
 if '--collect' in sys.argv:
  # Collection failure keeps already observed valid data; retry on the next hourly invocation.
  if os.environ.get('ZZ_COLLECTOR_URL'):
   import urllib.request
   state=json.loads((D/'observations.json').read_bytes()) if (D/'observations.json').exists() else {'schema':1,'episodes':{},'listings':{},'pending':[]}
   instant=datetime.datetime.now(datetime.timezone.utc)
   for attempt in range(1 if proof else 6):
    skip=[url for url,ep in state['episodes'].items() if (instant-datetime.datetime.fromisoformat(ep['observedAt'].replace('Z','+00:00'))).total_seconds()<6*86400 and not (ep.get('sourceSeries','').startswith('https://tioanime.com/') and all(p.get('family')=='mega' for p in ep.get('providers',[])))][-2500:]
    req=urllib.request.Request(os.environ['ZZ_COLLECTOR_URL'],data=raw({'skip':skip,'proof':proof,'checkPrimary':attempt==0}),headers={'Authorization':'Bearer '+os.environ['ZZ_COLLECTOR_KEY'],'Content-Type':'application/json','User-Agent':'ZZAnime-Data/1'},method='POST')
    with urllib.request.urlopen(req,timeout=60) as response:result=json.loads(response.read(2097153))
    if not result.get('passed'):raise ValueError('Cloud source unavailable; previous data retained')
    incoming=result['state'];state['episodes'].update(incoming['episodes']);state['listings'].update(incoming['listings']);put(D/'observations.json',raw(state))
    if not incoming['episodes']:break
  else:subprocess.run(['node',str(W/'collect.cjs')],env=dict(os.environ,ZZ_DATA=str(D)),check=False,timeout=420)
 state=json.loads((D/'observations.json').read_bytes());now=datetime.datetime.now(datetime.timezone.utc)
 with tempfile.TemporaryDirectory() as tmp:
  tmp=Path(tmp);cp=compile_java(tmp/'classes');queries={}
  for ep in state['episodes'].values():
   for p in ep.get('providers',[]):
    for url in p.get('links',[]):queries[sha((p['name']+'\0'+url).encode())]={'name':p['name'],'url':url}
  output=command(['java','-cp',cp,'tv.jkanime.web.RuntimeOptionAudit'],input='\n'.join(json.dumps(v) for v in queries.values()))
  approved={r['key']:r['approved'] for r in map(json.loads,output.splitlines())}
  if set(approved)!=set(queries):raise ValueError('Incomplete real app option validation')
  index,files=build(state,approved,now)
  if proof and (len(index['series'])!=2 or sum(x['episodes'] for x in index['series'].values())!=2):raise ValueError('Two-series proof incomplete; do not activate')
  public=(W/'public-key.der').read_bytes()
  private=os.environ.get('ZZ_SIGNING_KEY','')
  key=serialization.load_pem_private_key(private.encode(),None) if private else None
  if key and key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)!=public:raise ValueError('Installed app key differs')
  if not key:
   if '--publish' in sys.argv:raise ValueError('Cloud signing secret missing')
   key=rsa.generate_private_key(public_exponent=65537,key_size=2048);public=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
  site=tmp/'site';assets=site/'assets'
  digest=sha(raw(index));name='indexes/'+digest+'.bin';files[name]=raw(index)
  payload=raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':now.isoformat().replace('+00:00','Z'),'indexSha256':digest,'indexPath':name,'indexBytes':len(files[name]),'mode':'daily-new'})
  files['channel.json']=raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})
  files['_headers']=b'/channel.json\n  Cache-Control: public, max-age=300, must-revalidate\n/indexes/*\n  Cache-Control: public, max-age=31536000, immutable\n/series/*\n  Cache-Control: public, max-age=31536000, immutable\n'
  files['index.html']=b'<!doctype html><meta charset="utf-8"><title>ZZAnime</title><p>Canal de datos de ZZAnime.</p>'
  for n,b in files.items():put(assets/n,b)
  put(tmp/'key.der',public)
  proof_result=json.loads(command(['java','-cp',cp,'tv.jkanime.web.CloudVerify',str(assets),str(tmp/'key.der'),str(tmp/'cache')]))
  content=sha(raw(index['series']));prior=json.loads((D/'publication.json').read_bytes()) if (D/'publication.json').exists() else {}
  changed=prior.get('contentSha256')!=content or (now-datetime.datetime.fromisoformat(prior.get('publishedAt','2000-01-01T00:00:00+00:00'))).total_seconds()>86400
  report={**proof_result,'checkedAt':now.isoformat(),'proof':proof,'published':False,'changed':changed,'contentSha256':content,'aiCalls':0,'pcRequired':False}
  if '--publish' in sys.argv and changed:
   if not os.environ.get('CLOUDFLARE_API_TOKEN') and not (proof and '--local-proof-publication' in sys.argv):raise ValueError('Cloudflare publication secret missing')
   # Keep exactly one prior immutable generation; never publish arbitrary state/private files.
   old=D/'published-assets'
   if old.exists():
    import re
    for p in old.rglob('*.bin'):
     n=p.relative_to(old).as_posix()
     if re.fullmatch(r'(series|indexes)/[a-f0-9]{64}\.bin',n) and n not in files:put(assets/n,p.read_bytes())
   if len(list(assets.rglob('*')))>18000 or any(p.stat().st_size>2097152 for p in assets.rglob('*') if p.is_file()):raise ValueError('Static/app limits; paid upgrade forbidden')
   config={'name':'zzanime-respaldo','account_id':'3407d07c06229321d34863cf0fdac02d','compatibility_date':'2026-10-26','assets':{'directory':'./assets','not_found_handling':'none'},'send_metrics':False,'observability':{'enabled':False}}
   put(site/'wrangler.json',raw(config));cli=W/'node_modules/wrangler/bin/wrangler.js'
   command(['node',str(cli),'deploy','--config',str(site/'wrangler.json')],env=dict(os.environ,WRANGLER_SEND_METRICS='false'))
   remote=json.loads(command(['java','-cp',cp,'tv.jkanime.web.CloudVerify',str(assets),str(tmp/'key.der'),str(tmp/'remote-cache'),BASE]))
   if remote!=proof_result:raise ValueError('Remote app result differs')
   # Retain only current generation in state. The next deployment adds it as its prior generation.
   if old.exists():shutil.rmtree(old)
   for n,b in files.items():put(old/n,b)
   report.update(published=True,verifiedRemote=True,publishedAt=now.isoformat());put(D/'publication.json',raw(report))
  put(D/'verification.json',raw(report));print(json.dumps(report))
if __name__=='__main__':main()
