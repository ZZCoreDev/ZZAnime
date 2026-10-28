"""Separate cloud renewal: re-observe before expiry, retain genuine records on failure."""
from pathlib import Path
import argparse,base64,datetime,json,os,subprocess,sys,time,urllib.request,urllib.error,tempfile
from archive_state import load,save,merge,stamp

DAY=86400
LEAD_AGE=DAY
MAX_EPISODES=200
PROOF=['https://jkanime.net/psyren/4/','https://jkanime.net/dark-summoner-to-dekiteiru/4/']

def select(state,failures,now,limit):
    rows=[]
    for url,ep in state['episodes'].items():
        observed=stamp(ep.get('observedAt'));listing=state['listings'].get(url.rsplit('/',2)[0]+'/')
        if observed<0 or now-observed<LEAD_AGE or not listing or url not in listing.get('episodes',[]):continue
        if failures.get(url,{}).get('retryAt',0)>now:continue
        rows.append((observed,url))
    return [url for _,url in sorted(rows)[:limit]]

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
    text=f'{start}\n## Refresco automático del respaldo\nEstado: {status.get("state","unknown")}. Fallos pendientes: {failures}; capítulos vencidos pendientes: {overdue}.\n'
    if failures or overdue or status.get('state')=='failed':text+='Deuda: conservar observaciones originales; reintentar fuentes verificadas. No se han cambiado fechas para ocultar fallos.\n'
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
    if not select(state,failures,time.time(),1):return
    if os.environ.get('GITHUB_REPOSITORY')!='ZZCoreDev/ZZAnime':raise ValueError('Continuation repository not allowed')
    # GitHub keeps only one pending job per concurrency group. Never replace waiting news.
    pending=urllib.request.Request('https://api.github.com/repos/ZZCoreDev/ZZAnime/actions/workflows/provider-hourly.yml/runs?per_page=20',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'ZZAnime-Renewal/1'})
    with urllib.request.urlopen(pending,timeout=20) as response:runs=json.loads(response.read())['workflow_runs']
    if any(row.get('status') in ('queued','pending','waiting','in_progress','requested') for row in runs):
        print('Recent episode delivery has priority; renewal resumes after it completes.');return
    data=json.dumps({'ref':'main','inputs':{'proof':False}}).encode()
    req=urllib.request.Request('https://api.github.com/repos/ZZCoreDev/ZZAnime/actions/workflows/provider-renew.yml/dispatches',data=data,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'ZZAnime-Renewal/1'},method='POST')
    with urllib.request.urlopen(req,timeout=20) as response:
        if response.status!=204:raise ValueError('Continuation was not accepted')
    print('Pending observed chapters: next independent renewal batch dispatched.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--proof',action='store_true');parser.add_argument('--publish',action='store_true');parser.add_argument('--write-status');parser.add_argument('--continue-if-due',action='store_true');args=parser.parse_args()
    folder=Path(os.environ['ZZ_DATA']);folder.mkdir(parents=True,exist_ok=True);report=folder/'renewal-status.json'
    if args.continue_if_due:continue_if_due(folder);return
    if args.write_status:
        status=json.loads(report.read_bytes())
        if args.write_status=='github':github_status(status)
        else:status_document(Path(args.write_status),status)
        return
    state=load(folder);failure_path=folder/'renewal-failures.json';failures=json.loads(failure_path.read_bytes()) if failure_path.exists() else {};instant=time.time()
    targets=PROOF if args.proof else select(state,failures,instant,MAX_EPISODES)
    if args.proof and any(url not in state['episodes'] for url in targets):raise ValueError('Proof requires two existing real observations')
    status={'state':'running','checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'requested':len(targets),'renewed':0,'failed':len(failures),'datesInvented':False,'pcRequired':False,'aiCalls':0,'trigger':os.environ.get('GITHUB_EVENT_NAME','local'),'runId':os.environ.get('GITHUB_RUN_ID','')}
    publish=False;runtime=None
    try:
        for at in range(0,len(targets),2):
            if not args.proof and time.time()-instant>11*60:break
            pair=targets[at:at+2];before=time.time()
            try:
                body=json.dumps({'mode':'renew','retry':pair,'skip':[]}).encode()
                req=urllib.request.Request(os.environ['ZZ_COLLECTOR_URL'],data=body,headers={'Authorization':'Bearer '+os.environ['ZZ_COLLECTOR_KEY'],'Content-Type':'application/json','User-Agent':'ZZAnime-Data/1'},method='POST')
                with urllib.request.urlopen(req,timeout=90) as response:
                    raw=response.read(2097153)
                    if len(raw)>2097152:raise ValueError('Response limit')
                    result=json.loads(raw)
                if result.get('passed') is not True:raise ValueError('Sources unavailable')
                incoming=validate(result.get('state'),pair,before,time.time())
                for url in pair:
                    if url not in incoming.get('episodes',{}):raise ValueError('Requested renewal unavailable')
                # Use the real app validator before replacing any previous options.
                import run as pipeline
                if runtime is None:
                    runtime=tempfile.TemporaryDirectory();cp=pipeline.compile_java(Path(runtime.name)/'classes')
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
                for url in pair:failures.pop(url,None)
            except Exception as error:
                if isinstance(error,urllib.error.HTTPError) and error.code in (401,403,429):raise
                for url in pair:
                    count=failures.get(url,{}).get('attempts',0)+1
                    delay=7*DAY if count>=3 else min(6*3600,900*2**count)
                    failures[url]={'attempts':count,'lastAttempt':time.time(),'retryAt':time.time()+delay,'reason':('HTTP_'+str(error.code) if isinstance(error,urllib.error.HTTPError) else type(error).__name__)}
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
        report.write_text(json.dumps(status,indent=2),encoding='utf-8')
        print(json.dumps(status))

if __name__=='__main__':main()
