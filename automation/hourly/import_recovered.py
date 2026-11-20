"""Validated incremental import through the existing signed channel; never re-collects."""
from pathlib import Path
import datetime,gzip,json,os,re,subprocess,sys,tempfile
from archive_state import load,save,merge,stamp
import run as pipeline
from extra_channel import JK_NEWS_FOLDER

JK_FAMILIES={'mega','streamwish','vidhide','mixdrop','mp4upload','streamtape','filemoon'}

def check_batch(batch):
    if batch.get('schema')!=1 or not batch.get('proof',{}).get('allTwoPlayed'):raise ValueError('Two playback proofs required')
    if len(batch['state'].get('episodes',{}))>5000:raise ValueError('Bounded import exceeded')

def prepare(batch,current,approved,now,replace=False):
    # A newer real PC observation may replace an existing chapter; older or equal never does.
    check_batch(batch)
    source=batch['state'];catalogue={r['url']:r for r in json.loads(Path(__file__).with_name('catalogue.json').read_bytes())}
    incoming={'episodes':{},'listings':{}};held={};reused=0
    for url,ep in source.get('episodes',{}).items():
        old=current['episodes'].get(url)
        if old is not None and (not replace or stamp(ep.get('observedAt'))<=stamp(old.get('observedAt'))):reused+=1;continue
        parent=url.rsplit('/',2)[0]+'/';listing=source.get('listings',{}).get(parent);row=catalogue.get(parent)
        if not row or not listing or not listing.get('complete') or listing.get('title')!=row['title'] or url not in listing.get('episodes',[]):raise ValueError('Unobserved imported identity')
        numbers=listing['episodes']
        if ep.get('episode')!=url or len(set(numbers))!=len(numbers) or any(not re.fullmatch(re.escape(parent)+r'[1-9][0-9]*/',item) for item in numbers):raise ValueError('Invalid observed chapter identity')
        if not 0<=now.timestamp()-stamp(ep.get('observedAt'))<=7*86400 or not ep.get('complete'):held[url]='Incomplete or stale original observation';continue
        if not any(approved.get(pipeline.sha((p['name']+'\0'+link).encode())) for p in ep.get('providers',[]) for link in p.get('links',[])):held[url]='No app-approved provider';continue
        incoming['episodes'][url]=ep;incoming['listings'][parent]=listing
    if incoming['episodes']:pipeline.build(incoming,approved,now)
    return incoming,held,reused

def split_pc_news(batch,current,approved):
    normal={};news={}
    for url,ep in batch['state']['episodes'].items():
        if ep.get('pcNews') is not True:
            normal[url]=ep
            continue
        if ep.get('extraction')!='embedded-server-table':
            raise ValueError('JK news must come from a verified server table')
        # The Java validator is name-based. Store only its approved links under the matching family.
        providers=[]
        for p in ep.get('providers',[]):
            family=p.get('family')
            label=p['name'].strip().lower()
            match=re.fullmatch(r'([a-z]+)(?:[\s0-9:()_-].*)?',label)
            if not match or family not in JK_FAMILIES or family!=('streamtape' if match[1]=='streamtap' else match[1]):continue
            links=[u for u in p.get('links',[]) if approved.get(pipeline.sha((p['name']+'\0'+u).encode()))]
            if links:providers.append({'family':family,'name':p['name'],'links':links})
        news[url]={**ep,'providers':providers}
        if url not in current['episodes']:normal[url]=news[url]
    return tuple({**batch,'state':{**batch['state'],'episodes':part}} for part in (normal,news))

def main(publish=False,pc=False):
    # pc: the PC's continuous JK copy (outputs/catalog-lab/provider-refresh), fetched by the workflow from branch pc-import.
    folder=Path(os.environ['ZZ_DATA']);path=Path(os.environ['ZZ_PC_BATCH']) if pc else next((c for c in (folder.parent/'recovered-batch.json',Path(__file__).with_name('recovered-batch.json')) if c.exists()),Path(__file__).with_name('recovered-batch.json'));raw_batch=path.read_bytes();batch=json.loads(gzip.decompress(raw_batch) if pc else raw_batch);current=load(folder)
    check_batch(batch)
    before={url:ep['observedAt'] for url,ep in current['episodes'].items()};now=datetime.datetime.now(datetime.timezone.utc)
    side_folder=folder/JK_NEWS_FOLDER
    side=load(side_folder) if pc else None
    side_incoming={'episodes':{},'listings':{}}
    with tempfile.TemporaryDirectory(dir=folder.parent) as temp:
        cp=pipeline.compile_java(Path(temp)/'classes');queries={pipeline.sha((p['name']+'\0'+u).encode()):{'name':p['name'],'url':u} for ep in batch['state']['episodes'].values() for p in ep.get('providers',[]) for u in p.get('links',[])}
        output=pipeline.command(['java','-cp',cp,'tv.jkanime.web.RuntimeOptionAudit'],input='\n'.join(json.dumps(v) for v in queries.values()))
        approved={r['key']:r['approved'] for r in map(json.loads,output.splitlines())}
        if pc:
            batch,news=split_pc_news(batch,current,approved)
            if news['state']['episodes']:
                side_incoming,side_held,side_reused=prepare(news,side,approved,now,replace=True)
        incoming,held,reused=prepare(batch,current,approved,now,replace=pc)
    merge(current,incoming)
    if not all(current['episodes'][url]['observedAt']==date or (url in incoming['episodes'] and stamp(current['episodes'][url]['observedAt'])>stamp(date)) for url,date in before.items()): raise AssertionError()
    if incoming['episodes']:save(folder,current,set(incoming['listings']))
    if side_incoming['episodes']:
        merge(side,side_incoming)
        save(side_folder,side,set(side_incoming['listings']))
    if pc and news['state']['episodes']:
        held.update(side_held)
        reused+=side_reused
    imported=incoming['episodes'].keys()|side_incoming['episodes'].keys()
    digest=pipeline.sha(raw_batch);status=folder/('pc-import-status.json' if pc else 'recovered-import-status.json')
    previous=json.loads(status.read_bytes()) if pc and status.exists() else {}
    acknowledged=previous.get('batchSha256')==digest and previous.get('published') is True
    report={'batchSha256':digest,'checkedAt':now.isoformat(),'state':'imported' if imported else 'unchanged','imported':len(imported),'supplemented':len(side_incoming['episodes']),'series':len(incoming['listings'].keys()|side_incoming['listings'].keys()),'reused':reused,'held':held,'originalDatesPreserved':True,'sourceRequests':0,'published':acknowledged}
    # The workflow retains observations even if deployment fails. Reused rows can still need publication.
    if publish and (imported or pc and reused and not acknowledged):
        subprocess.run([sys.executable,str(Path(__file__).with_name('run.py')),'--publish'],check=True)
        report['published']=True
    status.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
