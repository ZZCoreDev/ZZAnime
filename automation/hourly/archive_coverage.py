"""Whole-catalogue coverage using observed identities only. No source/media requests."""
from collections import defaultdict,Counter
from pathlib import Path
import csv,datetime,gzip,json
from archive_state import stamp
from functools import lru_cache

@lru_cache(maxsize=1)
def baseline():
    path=Path(__file__).with_name('coverage-baseline.json.gz')
    return json.loads(gzip.decompress(path.read_bytes())) if path.exists() else {'series':{}}

def missing_targets(state,failures,now):
    observed={parent:set(row['episodes']) for parent,row in baseline().get('series',{}).items()}
    for parent,row in state.get('listings',{}).items():observed.setdefault(parent,set()).update(row.get('episodes',[]))
    return sorted(url for urls in observed.values() for url in urls if url not in state['episodes'] and failures.get(url,{}).get('retryAt',0)<=now)

def audit(catalogue,baseline,state,failures,now):
    by_parent=defaultdict(dict);failed_by_parent=defaultdict(list)
    for url,ep in state.get('episodes',{}).items():by_parent[url.rsplit('/',2)[0]+'/'][url]=ep
    for url in failures:failed_by_parent[url.rsplit('/',2)[0]+'/'].append(url)
    groups=defaultdict(list);rows=[];totals=Counter()
    for item in catalogue:
        parent=item['url'];old=baseline.get('series',{}).get(parent,{});current=state.get('listings',{}).get(parent,{})
        observed=set(old.get('episodes',[]))|set(current.get('episodes',[]));saved=by_parent[parent];missing=sorted(observed-set(saved));expired=[];empty=[];families=Counter()
        for url,ep in saved.items():
            if not 0<=now-stamp(ep.get('observedAt'))<=7*86400:expired.append(url)
            providers=[p for p in ep.get('providers',[]) if p.get('links')]
            if not providers:empty.append(url)
            for p in providers:families[p.get('family','unknown')]+=1
        failed=sorted(failed_by_parent[parent]);redirects=[url for url in missing if 'redirect' in baseline.get('retained',{}).get(url,'').lower()]
        causes=[]
        if not observed:causes.append('no-observed-listing')
        if missing:causes.append('observed-chapters-without-options')
        if redirects:causes.append('retained-redirect')
        if expired:causes.append('expired-observation')
        if empty:causes.append('no-independent-option')
        if failed:causes.append('renewal-error')
        row={'series':parent,'title':item['title'],'causes':causes,'observed':len(observed),'stored':len(saved),'missing':missing,'expired':expired,'noIndependent':empty,'renewalFailed':len(failed),'families':dict(families),'playbackVerified':False}
        rows.append(row)
        for cause in causes:groups[cause].append({'series':parent,'title':item['title'],'samples':(redirects if cause=='retained-redirect' else missing or expired or empty or failed)[:2]})
        totals.update(observedChapters=len(observed),storedChapters=len(saved),missingChapters=len(missing),expiredChapters=len(expired),noIndependentChapters=len(empty),seriesWithoutObservedListing=int(not observed))
    return {'checkedAt':datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat(),'catalogueSeries':len(catalogue),**dict(totals),'sourceRequests':0,'aiCalls':0,'playbackVerified':False,'groups':dict(groups),'series':rows}

def write(folder,report):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    (folder/'archive-coverage.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    queue={cause:{'series':len(rows),'twoSeriesProofRequired':True,'samples':rows[:2]} for cause,rows in report['groups'].items()}
    (folder/'repair-queue.json').write_text(json.dumps(queue,indent=2,ensure_ascii=False),encoding='utf-8')
    with (folder/'archive-coverage.csv').open('w',encoding='utf-8-sig',newline='') as f:
        out=csv.writer(f);out.writerow(['title','series','causes','observed','stored','missing','expired','renewalFailed'])
        for row in report['series']:out.writerow([row['title'],row['series'],' | '.join(row['causes']),row['observed'],row['stored'],len(row['missing']),len(row['expired']),row['renewalFailed']])
    summary={k:v for k,v in report.items() if k not in ['groups','series']}
    lines=['# Cobertura completa del respaldo','',json.dumps(summary,ensure_ascii=False),'','Presencia de opciones no demuestra reproducción. Los títulos sin listado observado tienen disponibilidad desconocida; no se inventan capítulos.','']
    lines.extend('- '+cause+': '+str(len(rows))+' series.' for cause,rows in report['groups'].items())
    (folder/'archive-coverage.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary

def cloud_report(folder,state,failures,now):
    root=Path(__file__).parent;path=root/'coverage-baseline.json.gz'
    if not path.exists():return {'state':'baseline-not-installed'}
    return write(folder,audit(json.loads((root/'catalogue.json').read_bytes()),json.loads(gzip.decompress(path.read_bytes())),state,failures,now))
