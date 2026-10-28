"""Validated incremental import through the existing signed channel; never re-collects."""
from pathlib import Path
import datetime,json,os,re,subprocess,sys,tempfile
from archive_state import load,save,merge,stamp
import run as pipeline

def prepare(batch,current,approved,now):
    if batch.get('schema')!=1 or not batch.get('proof',{}).get('allTwoPlayed'):raise ValueError('Two playback proofs required')
    source=batch['state'];catalogue={r['url']:r for r in json.loads(Path(__file__).with_name('catalogue.json').read_bytes())}
    if len(source.get('episodes',{}))>5000:raise ValueError('Bounded import exceeded')
    incoming={'episodes':{},'listings':{}};held={};reused=0
    for url,ep in source.get('episodes',{}).items():
        if url in current['episodes']:reused+=1;continue
        parent=url.rsplit('/',2)[0]+'/';listing=source.get('listings',{}).get(parent);row=catalogue.get(parent)
        if not row or not listing or not listing.get('complete') or listing.get('title')!=row['title'] or url not in listing.get('episodes',[]):raise ValueError('Unobserved imported identity')
        numbers=listing['episodes']
        if ep.get('episode')!=url or len(set(numbers))!=len(numbers) or any(not re.fullmatch(re.escape(parent)+r'[1-9][0-9]*/',item) for item in numbers):raise ValueError('Invalid observed chapter identity')
        if not 0<=now.timestamp()-stamp(ep.get('observedAt'))<=7*86400 or not ep.get('complete'):held[url]='Incomplete or stale original observation';continue
        if not any(approved.get(pipeline.sha((p['name']+'\0'+link).encode())) for p in ep.get('providers',[]) for link in p.get('links',[])):held[url]='No app-approved provider';continue
        incoming['episodes'][url]=ep;incoming['listings'][parent]=listing
    if incoming['episodes']:pipeline.build(incoming,approved,now)
    return incoming,held,reused

def main(publish=False):
    folder=Path(os.environ['ZZ_DATA']);path=Path(__file__).with_name('recovered-batch.json');batch=json.loads(path.read_bytes());current=load(folder)
    before={url:ep['observedAt'] for url,ep in current['episodes'].items()};now=datetime.datetime.now(datetime.timezone.utc)
    with tempfile.TemporaryDirectory(dir=folder.parent) as temp:
        cp=pipeline.compile_java(Path(temp)/'classes');queries={pipeline.sha((p['name']+'\0'+u).encode()):{'name':p['name'],'url':u} for ep in batch['state']['episodes'].values() for p in ep.get('providers',[]) for u in p.get('links',[])}
        output=pipeline.command(['java','-cp',cp,'tv.jkanime.web.RuntimeOptionAudit'],input='\n'.join(json.dumps(v) for v in queries.values()))
        approved={r['key']:r['approved'] for r in map(json.loads,output.splitlines())}
        incoming,held,reused=prepare(batch,current,approved,now)
    merge(current,incoming)
    assert all(current['episodes'][url]['observedAt']==date for url,date in before.items())
    if incoming['episodes']:save(folder,current,set(incoming['listings']))
    report={'batchSha256':pipeline.sha(path.read_bytes()),'checkedAt':now.isoformat(),'state':'imported' if incoming['episodes'] else 'unchanged','imported':len(incoming['episodes']),'series':len(incoming['listings']),'reused':reused,'held':held,'originalDatesPreserved':True,'sourceRequests':0,'published':False}
    (folder/'recovered-import-status.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if incoming['episodes'] and publish:
        subprocess.run([sys.executable,str(Path(__file__).with_name('run.py')),'--publish'],check=True)
        report['published']=True
    (folder/'recovered-import-status.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
