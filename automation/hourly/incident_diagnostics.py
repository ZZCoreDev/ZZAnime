"""No source requests: fair retries and one compact diagnosis per failed series."""
from collections import defaultdict,deque,Counter
import datetime,json
from pathlib import Path

def fair_retries(rows,failures):
    groups=defaultdict(deque)
    for row in rows:groups[row[1].rsplit('/',2)[0]+'/'].append(row)
    # First inspect a different series, rather than 100 chapters of one broken address.
    # Series just released by a verified identity alias go first; the mark is gone after their next attempt.
    ordered=sorted(groups,key=lambda parent:(not any(failures.get(r[1],{}).get('identityReleased') for r in groups[parent]),any(failures.get(r[1],{}).get('diagnostic') for r in groups[parent]),groups[parent][0]))
    result=[]
    while ordered:
        for parent in ordered:result.append(groups[parent].popleft())
        ordered=[parent for parent in ordered if groups[parent]]
    return result

def report(folder,failures,now):
    groups=defaultdict(list)
    for url,item in failures.items():groups[url.rsplit('/',2)[0]+'/'].append((url,item))
    rows=[];causes=Counter();covered=0;final_reasons=Counter()
    for parent,items in sorted(groups.items(),key=lambda p:-len(p[1])):
        observed=[(url,item) for url,item in items if item.get('diagnostic')]
        latest=max(observed,key=lambda pair:pair[1].get('lastAttempt',0)) if observed else None
        sources=latest[1]['diagnostic'] if latest else {};covered+=bool(observed)
        final_reasons.update(str(item.get('reason','unknown')) for _,item in items)
        for source,value in sources.items():causes[source+':'+value.get('cause','unknown')]+=1
        rows.append({'series':parent,'failedChapters':len(items),'samples':[u for u,_ in items[:2]],'diagnosedSample':latest[0] if latest else None,'sources':sources,'sampleOnly':True,'automaticApproval':False,'nextRetryAt':min(x.get('retryAt',now) for _,x in items)})
    value={'checkedAt':datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat(),'failedChapters':len(failures),'series':len(groups),'diagnosedSeries':covered,'pendingSeries':len(groups)-covered,'causes':dict(causes),'knownFinalReasons':dict(final_reasons),'sourceRequests':0,'aiCalls':0,'automaticApproval':False,'groups':rows}
    Path(folder,'renewal-diagnostics.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    lines=['# Diagnóstico automático por serie','',f'{covered}/{len(groups)} series con diagnóstico detallado; {len(failures)} capítulos con fallo. Sin consultas adicionales ni IA.','La muestra clasifica la causa; no demuestra que todos sus capítulos fallen igual ni aprueba enlaces.','']
    for row in rows:
        detail='; '.join(source+': '+v.get('cause','unknown')+' / '+v.get('stage','unknown') for source,v in row['sources'].items()) or 'pendiente del próximo reintento permitido'
        lines.append('- '+row['series']+': '+str(row['failedChapters'])+' capítulos. '+detail)
    Path(folder,'renewal-diagnostics.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return {key:value[key] for key in ['series','diagnosedSeries','pendingSeries']}
