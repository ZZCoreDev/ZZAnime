"""Separate cloud renewal: re-observe before expiry, retain genuine records on failure."""
from pathlib import Path
import argparse,base64,datetime,json,os,subprocess,sys,time,urllib.request,urllib.error,tempfile,hashlib
from archive_state import load,save,merge,stamp
from incident_diagnostics import fair_retries,report as diagnostic_report
from news_watchdog import check as check_news

DAY=86400
LEAD_AGE=DAY
MAX_EPISODES=400
PROOF=['https://jkanime.net/psyren/4/','https://jkanime.net/dark-summoner-to-dekiteiru/4/']
INCIDENT_PROOF=['https://jkanime.net/mao/1/','https://jkanime.net/psyren/4/']

def repair_verified_identities(state,failures,now):
    path=Path(__file__).with_name('source-identities.json');catalog=Path(__file__).with_name('catalogue.json')
    if not path.exists() or not catalog.exists():return 0
    rows={r['url']:r for r in json.loads(catalog.read_bytes())};repaired=0
    for parent,entry in json.loads(path.read_bytes()).items():
        row=rows.get(parent,{})
        if not entry.get('approved') or row.get('year')!=entry['year'] or row.get('title','').casefold()!=entry['title'].casefold():continue
        revision=hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest();done=state.setdefault('identityRepairs',{})
        if done.get(parent)==revision:continue
        for url,failure in failures.items():
            ep=state['episodes'].get(url)
            if url.rsplit('/',2)[0]+'/'==parent and ep and now-stamp(ep['observedAt'])>=LEAD_AGE:
                failure['previousRetryAt']=failure.get('retryAt',0);failure['retryAt']=now;repaired+=1
        done[parent]=revision
    return repaired

def select(state,failures,now,limit,include_missing=False):
    rows=[]
    for url,ep in state['episodes'].items():
        observed=stamp(ep.get('observedAt'));listing=state['listings'].get(url.rsplit('/',2)[0]+'/')
        if observed<0 or now-observed<LEAD_AGE or not listing or url not in listing.get('episodes',[]):continue
        if failures.get(url,{}).get('retryAt',0)>now:continue
        rows.append((observed,url))
    healthy=sorted(row for row in rows if row[1] not in failures);retry=fair_retries(sorted(row for row in rows if row[1] in failures),failures)
    from archive_coverage import missing_targets
    missing=fair_retries([(0,url) for url in missing_targets(state,failures,now)],failures) if include_missing else []
    repair_limit=max(1,limit//4) if healthy else limit
    missing_count=min(len(missing),max(1,repair_limit//2)) if missing else 0
    retry_count=min(len(retry),repair_limit-missing_count)
    chosen=healthy[:limit-retry_count-missing_count]+retry[:retry_count]+missing[:missing_count]
    seen={url for _,url in chosen}
    if len(chosen)<limit:chosen+=(row for row in retry[retry_count:]+missing[missing_count:] if row[1] not in seen)
    chosen=chosen[:limit]
    # The time budget often ends before the tail of a 400-item list. Enforce
    # the existing 75/25 allocation in each prefix, not only at list completion.
    healthy_queue=[row for row in chosen if row[1] in state['episodes'] and row[1] not in failures]
    failed_queue=[row for row in chosen if row[1] in failures and row[1] in state['episodes']]
    missing_queue=[row for row in chosen if row[1] not in state['episodes']]
    repair_queue=[]
    while failed_queue or missing_queue:
        if failed_queue:repair_queue.append(failed_queue.pop(0))
        if missing_queue:repair_queue.append(missing_queue.pop(0))
    ordered=[]
    while healthy_queue or repair_queue:
        ordered.extend(healthy_queue[:3]);del healthy_queue[:3]
        if repair_queue:ordered.append(repair_queue.pop(0))
    return [url for _,url in ordered]

def record_failure(failures,url,reason,now,observed,diagnostic=None):
    count=failures.get(url,{}).get('attempts',0)+1
    delay=min(6*3600,900*2**min(count,8));observed_stamp=stamp(observed)
    if observed_stamp>=0:
        remaining=observed_stamp+7*DAY-now;delay=min(delay,remaining/3) if remaining>0 else 900
    previous=failures.get(url,{}).get('diagnostic')
    failures[url]={'attempts':count,'lastAttempt':now,'retryAt':now+delay,'reason':str(reason)[:160]}
    if diagnostic or previous:failures[url]['diagnostic']=diagnostic or previous

def repair_retry_deadlines(state,failures,now):
    repaired=0
    for url,row in failures.items():
        ep=state['episodes'].get(url)
        if not ep:continue
        deadline=stamp(ep.get('observedAt'))+7*DAY
        if row.get('retryAt',0)>deadline and row.get('retryAt',0)>now and (deadline>now or row['retryAt']>now+3600):
            row.setdefault('previousRetryAt',row['retryAt']);remaining=deadline-now
            row['retryAt']=now+(min(3600,remaining/3) if remaining>0 else 900);repaired+=1
    return repaired

def health_report(folder,state,failures,status,now):
    ages={url:now-stamp(ep.get('observedAt')) for url,ep in state['episodes'].items()}
    path=folder/'renewal-history.json';history=json.loads(path.read_bytes()) if path.exists() else []
    start=stamp(status['checkedAt']);row={'runId':status.get('runId',''),'start':start,'finish':now,'renewed':status.get('renewed',0),'proof':status.get('proof',False),'published':status.get('published',False)}
    history=[r for r in history if r['start']>=now-14*DAY and not (row['runId'] and r.get('runId')==row['runId'])]+[row]
    path.write_text(json.dumps(history[-5000:]),encoding='utf-8')
    usable=[r for r in history if not r.get('proof') and r.get('published') and r['start']>=now-DAY]
    measured_span=now-min((r['start'] for r in usable),default=now);span=max(3600,measured_span);rate=sum(r['renewed'] for r in usable)*3600/span
    qualified=len(usable)>=3 and measured_span>=3600
    eta=len(ages)/rate/24 if rate and qualified else None
    report={'checkedAt':datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat(),'episodes':len(ages),'oldestHours':round(max(ages.values(),default=0)/3600,2),'pending':len(select(state,failures,now,len(ages))),'expired':sum(age>7*DAY for age in ages.values()),'expiresWithin24Hours':sum(age>=6*DAY for age in ages.values()),'retryAfterExpiry':sum(r.get('retryAt',0)>now+7*DAY-ages[url] for url,r in failures.items() if url in ages),'successfulCyclesMeasured':len(usable),'sampleMinutes':round(measured_span/60,2),'measuredWallClockPerHour':round(rate,2),'estimatedSweepDays':round(eta,2) if eta is not None else None,'capacityStatus':'insufficient-history' if not qualified else 'within-budget' if eta is not None and eta<=5 else 'behind','datesInvented':False}
    identity_path=Path(__file__).with_name('source-identities.json');recovery={}
    if identity_path.exists():
        for parent,entry in json.loads(identity_path.read_bytes()).items():
            if not entry.get('approved'):continue
            urls=[url for url in ages if url.rsplit('/',2)[0]+'/'==parent]
            if not urls:continue
            fresh=sum(0<=ages[url]<DAY for url in urls);pending=sum(url in failures for url in urls)
            recovery[parent]={'title':entry['title'],'total':len(urls),'fresh':fresh,'pendingFailures':pending,'state':'complete' if fresh==len(urls) and pending==0 else 'pending'}
    report['verifiedIdentityRecovery']=recovery
    report['incidentDiagnosis']=diagnostic_report(folder,failures,now)
    from archive_coverage import cloud_report
    report['coverage']=cloud_report(folder,state,failures,now)
    (folder/'renewal-health.json').write_text(json.dumps(report,indent=2),encoding='utf-8');return report

def validate(incoming,targets,before,after):
    if not isinstance(incoming,dict):raise ValueError('Missing observations')
    if set(incoming.get('episodes',{}))-set(targets):raise ValueError('Unrequested episode returned')
    for url,ep in incoming.get('episodes',{}).items():
        parent=url.rsplit('/',2)[0]+'/';listing=incoming.get('listings',{}).get(parent)
        if not listing or not listing.get('complete') or url not in listing.get('episodes',[]):raise ValueError('Observed listing mismatch')
        if not ep.get('complete') or not ep.get('providers'):raise ValueError('No complete options')
        for date in (ep.get('observedAt'),listing.get('observedAt')):
            if not before-60<=stamp(date)<=after+60:raise ValueError('No fresh source observation')
    return incoming

def status_text(current,status):
    start='<!-- ZZ-RENEW-STATUS -->';end='<!-- /ZZ-RENEW-STATUS -->'
    failures=status.get('failed',0);overdue=status.get('expired',0)
    text=f'{start}\n## Refresco automático del respaldo\nEstado: {status.get("state","unknown")}. Fallos pendientes: {failures}; capítulos vencidos pendientes: {overdue}. Próximos a vencer: {status.get("expiresWithin24Hours","pendiente")}; capacidad: {status.get("capacityStatus","sin medir")}.\n'
    if failures or overdue or status.get('state')=='failed':text+='Deuda: conservar observaciones originales; reintentar fuentes verificadas. No se han cambiado fechas para ocultar fallos.\n'
    for group in status.get('verifiedIdentityRecovery',{}).values():text+=f'Equivalencia comprobada: {group["title"]}, {group["fresh"]}/{group["total"]} capítulos recientes; incidencias pendientes: {group["pendingFailures"]}.\n'
    diagnosis=status.get('incidentDiagnosis',{})
    if diagnosis:text+=f'Diagnóstico por serie: {diagnosis["diagnosedSeries"]}/{diagnosis["series"]}; pendientes: {diagnosis["pendingSeries"]}. Sin consultas adicionales ni aprobación automática. Detalle: provider-data/state/renewal-diagnostics.md.\n'
    coverage=status.get('archiveCoverage',{})
    if 'catalogueSeries' in coverage:text+=f'Cobertura de catálogo: {coverage["catalogueSeries"]} títulos, {coverage["storedChapters"]} capítulos con registros, {coverage["missingChapters"]} capítulos observados sin opciones y {coverage["expiredChapters"]} vencidos. Presencia no equivale a reproducción. Detalle: state/archive-coverage.md.\n'
    text+=end
    if start in current and end in current:
        a=current.index(start);b=current.index(end,a)+len(end);updated=current[:a]+text+current[b:]
    else:updated=current.rstrip()+'\n\n'+text+'\n'
    return updated

def status_document(path,status):
    current=path.read_text(encoding='utf-8') if path.exists() else '# ZZAnime\n';updated=status_text(current,status)
    if updated!=current:path.write_text(updated,encoding='utf-8')

def github_status(status):
    repo=os.environ.get('GITHUB_REPOSITORY','')
    if repo!='ZZCoreDev/ZZAnime':raise ValueError('Status repository not allowed')
    endpoint='https://api.github.com/repos/'+repo+'/contents/ESTADO.md'
    headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'ZZAnime-Renewal/1','Content-Type':'application/json'}
    for attempt in range(4):
        with urllib.request.urlopen(urllib.request.Request(endpoint+'?ref=main',headers=headers),timeout=20) as response:old=json.load(response)
        current=base64.b64decode(old['content']).decode('utf-8');updated=status_text(current,status)
        if updated==current:return
        data=json.dumps({'message':'Registrar estado de renovacion sin sobrescribir cambios concurrentes','branch':'main','sha':old['sha'],'content':base64.b64encode(updated.encode()).decode()}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(endpoint,data=data,headers=headers,method='PUT'),timeout=20) as response:json.load(response)
            return
        except urllib.error.HTTPError as error:
            if error.code not in (409,422) or attempt==3:raise
            time.sleep(attempt+1)

def continue_if_due(folder):
    status=json.loads((folder/'renewal-status.json').read_bytes())
    if status.get('state') not in ('complete','complete-with-failures'):return
    state=load(folder);failed_path=folder/'renewal-failures.json';failures=json.loads(failed_path.read_bytes()) if failed_path.exists() else {}
    if not select(state,failures,time.time(),1,include_missing=True):return
    if os.environ.get('GITHUB_REPOSITORY')!='ZZCoreDev/ZZAnime':raise ValueError('Continuation repository not allowed')
    # GitHub keeps only one pending job per concurrency group. Never replace waiting news.
    pending=urllib.request.Request('https://api.github.com/repos/ZZCoreDev/ZZAnime/actions/workflows/provider-hourly.yml/runs?per_page=20',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'ZZAnime-Renewal/1'})
    with urllib.request.urlopen(pending,timeout=20) as response:runs=json.loads(response.read())['workflow_runs']
    if any(row.get('status') in ('queued','pending','waiting','in_progress','requested') for row in runs):
        print('Recent episode delivery has priority; renewal resumes after it completes.');return
    pending_renew=urllib.request.Request('https://api.github.com/repos/ZZCoreDev/ZZAnime/actions/workflows/provider-renew.yml/runs?per_page=20',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'ZZAnime-Renewal/1'})
    with urllib.request.urlopen(pending_renew,timeout=20) as response:waiting=json.loads(response.read())['workflow_runs']
    if any(row.get('status') in ('queued','pending','waiting','requested') for row in waiting):
        print('A renewal or sample is already waiting; keep its place in the queue.');return
    data=json.dumps({'ref':'main','inputs':{'proof':False}}).encode()
    req=urllib.request.Request('https://api.github.com/repos/ZZCoreDev/ZZAnime/actions/workflows/provider-renew.yml/dispatches',data=data,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'ZZAnime-Renewal/1'},method='POST')
    with urllib.request.urlopen(req,timeout=20) as response:
        if response.status!=204:raise ValueError('Continuation was not accepted')
    print('Pending observed chapters: next independent renewal batch dispatched.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--proof',action='store_true');parser.add_argument('--sample-group',choices=['baseline','verified-year','observed-token','recovered-import','voe-proof'],default='baseline');parser.add_argument('--publish',action='store_true');parser.add_argument('--write-status');parser.add_argument('--continue-if-due',action='store_true');args=parser.parse_args()
    if args.sample_group=='voe-proof':
        from voe_channel import proof
        proof(args.publish);return
    if args.sample_group=='recovered-import':
        from import_recovered import main as import_batch
        import_batch(args.publish);return
    folder=Path(os.environ['ZZ_DATA']);folder.mkdir(parents=True,exist_ok=True);report=folder/'renewal-status.json'
    if args.continue_if_due:continue_if_due(folder);return
    if args.write_status:
        status=json.loads(report.read_bytes())
        if args.write_status=='github':github_status(status)
        else:status_document(Path(args.write_status),status)
        return
    if not args.proof and args.publish:check_news(folder)
    state=load(folder);failure_path=folder/'renewal-failures.json';failures=json.loads(failure_path.read_bytes()) if failure_path.exists() else {};instant=time.time()
    repaired=repair_retry_deadlines(state,failures,instant)
    identities_repaired=repair_verified_identities(state,failures,instant)
    proof_targets=json.loads(Path(__file__).with_name('observed-token-policy.json').read_bytes())['proof'] if args.sample_group=='observed-token' else INCIDENT_PROOF if args.sample_group=='verified-year' else PROOF
    targets=proof_targets if args.proof else select(state,failures,instant,MAX_EPISODES,include_missing=True)
    if not args.proof:
        from voe_channel import due_targets
        extras=due_targets(folder,failures,instant,MAX_EPISODES//4);targets=list(dict.fromkeys(extras+targets))[:MAX_EPISODES]
    if args.proof and any(url not in state['episodes'] for url in targets):raise ValueError('Proof requires two existing real observations')
    status={'state':'running','checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'requested':len(targets),'renewed':0,'attempted':0,'repairAttempts':0,'earlyRepairAttempts':0,'failed':len(failures),'datesInvented':False,'pcRequired':False,'aiCalls':0,'trigger':os.environ.get('GITHUB_EVENT_NAME','local'),'runId':os.environ.get('GITHUB_RUN_ID','')}
    status['retryDeadlinesRepaired']=repaired
    status['proof']=args.proof
    status['identityRetriesReleased']=identities_repaired
    publish=False;runtime=None
    try:
        for at in range(0,len(targets),2):
            if not args.proof and time.time()-instant>11*60:break
            if not args.proof and args.publish and check_news(folder):state=load(folder)
            pair=targets[at:at+2];before=time.time()
            if not args.proof:pair=[url for url in pair if url not in state['episodes'] or before-stamp(state['episodes'][url].get('observedAt'))>=LEAD_AGE or url in extras]
            if not pair:continue
            repair=[u for u in pair if u in failures or u not in state['episodes']]
            status['repairAttempts']+=len(repair)
            if status['attempted']<8:status['earlyRepairAttempts']+=len(repair)
            status['attempted']+=len(pair)
            try:
                body=json.dumps({'mode':'renew','retry':pair,'skip':[],'proof':args.proof}).encode()
                req=urllib.request.Request(os.environ['ZZ_COLLECTOR_URL'],data=body,headers={'Authorization':'Bearer '+os.environ['ZZ_COLLECTOR_KEY'],'Content-Type':'application/json','User-Agent':'ZZAnime-Data/1'},method='POST')
                with urllib.request.urlopen(req,timeout=90) as response:
                    raw=response.read(2097153)
                    if len(raw)>2097152:raise ValueError('Response limit')
                    result=json.loads(raw)
                if result.get('passed') is not True:raise ValueError('Sources unavailable')
                incoming=validate(result.get('state'),pair,before,time.time())
                from voe_channel import split
                incoming,voe_count=split(folder,incoming)
                if voe_count:status['voeRenewed']=status.get('voeRenewed',0)+voe_count;publish=True
                missing=[url for url in pair if url not in incoming.get('episodes',{})]
                for url in missing:record_failure(failures,url,result.get('errors',{}).get(url,'Source did not return a verified observation'),time.time(),state['episodes'].get(url,{}).get('observedAt',''),result.get('diagnostics',{}).get(url))
                if not incoming.get('episodes'):continue
                # Use the real app validator before replacing any previous options.
                import run as pipeline
                if runtime is None:
                    runtime=tempfile.TemporaryDirectory(dir=folder.parent);cp=pipeline.compile_java(Path(runtime.name)/'classes')
                queries={}
                for ep in incoming['episodes'].values():
                    for provider in ep['providers']:
                        for link in provider.get('links',[]):queries[pipeline.sha((provider['name']+'\0'+link).encode())]={'name':provider['name'],'url':link}
                output=pipeline.command(['java','-cp',cp,'tv.jkanime.web.RuntimeOptionAudit'],input='\n'.join(json.dumps(v) for v in queries.values()))
                approved={row['key']:row['approved'] for row in map(json.loads,output.splitlines())}
                checked={'episodes':{},'listings':{}}
                merge(checked,incoming)
                pipeline.build(checked,approved,datetime.datetime.now(datetime.timezone.utc))
                for url,ep in incoming['episodes'].items():
                    if not any(approved.get(pipeline.sha((p['name']+'\0'+u).encode())) for p in ep['providers'] for u in p.get('links',[])):raise ValueError('Real app rejected renewed options')
                merge(state,incoming);status['renewed']+=len(incoming['episodes']);publish=True
                for url in incoming['episodes']:failures.pop(url,None)
            except Exception as error:
                if isinstance(error,urllib.error.HTTPError) and error.code in (401,403,429):raise
                for url in pair:record_failure(failures,url,('HTTP_'+str(error.code) if isinstance(error,urllib.error.HTTPError) else type(error).__name__+': '+str(error)),time.time(),state['episodes'].get(url,{}).get('observedAt',''))
            finally:
                save(folder,state,{url.rsplit('/',2)[0]+'/' for url in pair});failure_path.write_text(json.dumps(failures,sort_keys=True),encoding='utf-8')
                status.update(failed=len(failures),expired=sum(time.time()-stamp(ep.get('observedAt'))>7*DAY for ep in state['episodes'].values()))
                report.write_text(json.dumps(status,indent=2),encoding='utf-8')
        if args.proof and status['renewed']!=2:raise ValueError('Two-series renewal proof failed')
        if publish and args.publish:
            subprocess.run([sys.executable,str(Path(__file__).with_name('run.py')),'--publish'],check=True)
        status['state']='complete' if not failures else 'complete-with-failures'
        status['published']=publish and args.publish
    except BaseException as error:
        status.update(state='failed',error=type(error).__name__);raise
    finally:
        if runtime is not None:runtime.cleanup()
        status.update(failed=len(failures),expired=sum(time.time()-stamp(ep.get('observedAt'))>7*DAY for ep in state['episodes'].values()))
        health=health_report(folder,state,failures,status,time.time());status.update(expiresWithin24Hours=health['expiresWithin24Hours'],retryAfterExpiry=health['retryAfterExpiry'],capacityStatus=health['capacityStatus'],verifiedIdentityRecovery=health['verifiedIdentityRecovery'],incidentDiagnosis=health['incidentDiagnosis'],archiveCoverage=health['coverage'])
        report.write_text(json.dumps(status,indent=2),encoding='utf-8')
        print(json.dumps(status))

if __name__=='__main__':main()
