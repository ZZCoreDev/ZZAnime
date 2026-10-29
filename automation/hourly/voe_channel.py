"""Capability-isolated signed additions. Legacy observations are never replaced by VOE."""
from pathlib import Path
import copy,datetime,json,os,re,subprocess,time,urllib.request
from archive_state import load,save,merge,stamp

PROOF=['https://jkanime.net/sasaki-to-pii-chan-season-2/4/','https://jkanime.net/sekai-saikyou-no-majo-hajimemashita/4/']

def split(folder,incoming):
    legacy=copy.deepcopy(incoming);extra={'episodes':{},'listings':{}};now=time.time()
    for url,ep in incoming.get('episodes',{}).items():
        providers=[p for p in ep.get('providers',[]) if p.get('family')=='voe']
        if not providers:continue
        parent=url.rsplit('/',2)[0]+'/'
        listing=incoming.get('listings',{}).get(parent)
        if not listing or not listing.get('complete') or url not in listing.get('episodes',[]) or not re.fullmatch(r'https://jkanime\.net/[a-zA-Z0-9_-]+/[1-9][0-9]*/',url):raise ValueError('VOE observation identity')
        if not ep.get('complete') or not 0<=now-stamp(ep.get('observedAt'))<=7*86400:raise ValueError('VOE observation date')
        for p in providers:
            if p.get('name','').strip().lower()!='voe' or not p.get('links') or any(not re.fullmatch(r'https://voe\.sx/e/[a-zA-Z0-9_-]+',u) for u in p['links']):raise ValueError('VOE provider scope')
        extra['episodes'][url]={**ep,'providers':providers};extra['listings'][parent]=listing
        legacy['episodes'][url]['providers']=[p for p in ep['providers'] if p.get('family')!='voe']
        if not any(p.get('links') for p in legacy['episodes'][url]['providers']):legacy['episodes'].pop(url)
    count=0
    if extra['episodes']:
        side=load(Path(folder)/'voe-state')
        for url,ep in list(extra['episodes'].items()):
            old=side['episodes'].get(url)
            if old and now-stamp(old.get('observedAt'))<6*86400 and old.get('providers')==ep['providers']:extra['episodes'].pop(url)
        count=len(extra['episodes'])
        if count:merge(side,extra);save(Path(folder)/'voe-state',side,set(extra['listings']))
    return legacy,count

def fresh_urls(folder,now):
    state=load(Path(folder)/'voe-state')
    return [u for u,e in sorted(state['episodes'].items(),key=lambda r:stamp(r[1].get('observedAt')),reverse=True) if 0<=now-stamp(e.get('observedAt'))<6*86400][:500]

def due_targets(folder,failures,now,limit):
    state=load(Path(folder)/'voe-state')
    return [u for u,e in sorted(state['episodes'].items(),key=lambda r:stamp(r[1].get('observedAt'))) if now-stamp(e.get('observedAt'))>=5*86400 and failures.get(u,{}).get('retryAt',0)<=now][:limit]

def render(folder,now,key,runtime):
    import run as p
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    state=load(Path(folder)/'voe-state')
    state['episodes']={u:e for u,e in state['episodes'].items() if 0<=now.timestamp()-stamp(e.get('observedAt'))<=7*86400}
    if not state['episodes']:return {},None,None
    cp=p.compile_java(Path(runtime)/'voe-classes',modern=True)
    queries={p.sha((v['name']+'\0'+u).encode()):{'name':v['name'],'url':u} for e in state['episodes'].values() for v in e['providers'] for u in v['links']}
    result=p.command(['java','-cp',cp,'tv.jkanime.web.RuntimeOptionAudit'],input='\n'.join(json.dumps(v) for v in queries.values()))
    approved={r['key']:r['approved'] for r in map(json.loads,result.splitlines())}
    index,files=p.build(state,approved,now,allow_voe=True);body=p.raw(index);digest=p.sha(body);name='indexes/'+digest+'.bin';files[name]=body
    payload=p.raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':now.isoformat().replace('+00:00','Z'),'indexSha256':digest,'indexPath':name,'indexBytes':len(body),'mode':'daily-new'})
    files['channel.json']=p.raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})
    return {'voe/'+n:b for n,b in files.items()},cp,p.sha(p.raw(index['series']))

def proof(publish=False):
    import run as p
    folder=Path(os.environ['ZZ_DATA']);folder.mkdir(parents=True,exist_ok=True)
    before=load(folder);original={u:json.dumps(e,sort_keys=True) for u,e in before['episodes'].items()}
    req=urllib.request.Request(os.environ['ZZ_COLLECTOR_URL'],data=p.raw({'mode':'renew','retry':PROOF,'skip':[],'voeProof':True}),headers={'Authorization':'Bearer '+os.environ['ZZ_COLLECTOR_KEY'],'Content-Type':'application/json','User-Agent':'ZZAnime-Data/1'},method='POST')
    with urllib.request.urlopen(req,timeout=90) as response:result=json.loads(response.read(2097153))
    if not result.get('passed') or set(result['state']['episodes'])!=set(PROOF):raise ValueError('Two-series VOE collection failed')
    legacy,count=split(folder,result['state']);after=load(folder)
    if any(json.dumps(after['episodes'][u],sort_keys=True)!=e for u,e in original.items()):raise ValueError('Legacy changed during VOE proof')
    side=load(folder/'voe-state')
    if any(not side['episodes'].get(u) for u in PROOF):raise ValueError('VOE proof incomplete')
    if publish:subprocess.run([os.sys.executable,str(Path(__file__).with_name('run.py')),'--publish'],check=True)
    report={'state':'complete','captured':count,'twoSeries':True,'legacyUnchanged':True,'published':publish,'physicalAndroidPlayback':False,'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (folder/'voe-proof-status.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
