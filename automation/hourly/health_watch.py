"""Health watchdog: deterministic alarms from provider-data, one GitHub issue per alarm kind, no AI.

Reads the provider-data state (publication, news watchdog, renewal, link health, help Worker, published
index) plus a small memory of its own (branch health-watch, state.json), and keeps exactly one open issue
per failing kind (label «vigia», marker <!-- vigia:<kind> -->). An issue is updated only when its text
changes and closed by itself, with a comment, once the check passes again. GitHub mails the owner."""
from pathlib import Path
import argparse,datetime,gzip,hashlib,json,os,urllib.error,urllib.request
HOUR=3600;DAY=86400
NEWS_HOURS=3;LINK_HEALTH_HOURS=3;WORKER_HOURS=24;FAILED_RISE=0.05;ZERO_RUNS=3
INDEX_LIMIT=int(1.8*1024*1024)
# Known secret expiry dates (Robin, 31/10/2026); warned 30 days ahead.
SECRETS={'GH_DISPATCH_TOKEN':'2027-01-28','ZZ_CLOUDFLARE_TOKEN':'2027-10-27'}
SECRET_NOTICE=30*DAY
LABEL='vigia'
def stamp(value):
    if isinstance(value,(int,float)):return float(value)
    try:return datetime.datetime.fromisoformat(str(value).replace('Z','+00:00')).timestamp()
    except ValueError:return -1.0
def iso(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
def read(folder,name,default=None):
    path=Path(folder)/name
    try:return json.loads(path.read_bytes())
    except (OSError,ValueError):return default
def published_urls(folder):
    channel=read(folder,'published-assets/channel.json')
    if not channel:return None,None
    payload=json.loads(channel['payload']);index=read(folder,'published-assets/'+payload['indexPath'])
    urls=set()
    for row in (index or {}).get('series',{}).values():
        try:urls|={e['url'] for e in json.loads(gzip.decompress((Path(folder)/'published-assets'/row['path']).read_bytes()))['episodes']}
        except (OSError,ValueError,KeyError):pass
    return payload,urls
def news_without_publication(folder,now,urls):
    """News seen more than 3 h ago (within 7 days) that have stored options but are not in the channel."""
    seen=(read(folder,'observations.json',{}) or {}).get('newsSeen',{});late=[]
    excluded={k for k,e in ((read(folder,'link-health.json',{}) or {}).get('links') or {}).items() if e.get('excluded')}
    for url,at in seen.items():
        age=now-stamp(at)
        if not NEWS_HOURS*HOUR<age<=7*DAY or url in urls:continue
        parent=url.rsplit('/',2)[0]+'/';shard=Path(folder)/'series-state'/(hashlib.sha256(parent.encode()).hexdigest()+'.json.gz')
        try:ep=json.loads(gzip.decompress(shard.read_bytes()))['episodes'].get(url)
        except (OSError,ValueError,KeyError):ep=None
        # VOE-only chapters go to the /voe/ complement; confirmed-deleted links are withdrawn on purpose.
        if ep and any(hashlib.sha256((p['name']+'\0'+l).encode()).hexdigest() not in excluded for p in ep.get('providers',[]) if p.get('family')!='voe' for l in p.get('links',[])):late.append(url)
    return sorted(late)
def check(folder,now,memory):
    """{kind: (failing, title, body)} and the updated memory."""
    out={};memory=dict(memory or {})
    def alarm(kind,failing,title,body=''):out[kind]=(bool(failing),title,body)
    publication=read(folder,'publication.json',{}) or {};payload,urls=published_urls(folder)
    if payload is None:
        alarm('datos',True,'No se puede leer el canal publicado de provider-data','Falta state/published-assets/channel.json o no es válido.');return out,memory
    alarm('datos',False,'Datos de provider-data legibles')
    pub_age=now-stamp(publication.get('publishedAt'));news=read(folder,'news-watchdog.json',{}) or {};news_age=now-stamp(news.get('attemptedAt'))
    late=news_without_publication(folder,now,urls or set())
    alarm('noticias',pub_age>NEWS_HOURS*HOUR or news_age>NEWS_HOURS*HOUR or late,'Noticias sin publicar en más de 3 h',
        f'Última publicación: {iso(stamp(publication.get("publishedAt")))}. Última comprobación de noticias: {iso(stamp(news.get("attemptedAt")))} ({news.get("state","?")}).\n'
        +(f'Capítulos vistos hace más de 3 h, con opciones guardadas y fuera del canal ({len(late)}):\n'+'\n'.join('- '+u for u in late[:30]) if late else ''))
    history=[r for r in (read(folder,'renewal-history.json',[]) or []) if not r.get('proof') and r.get('published')]
    last=history[-ZERO_RUNS:];status=read(folder,'renewal-status.json',{}) or {}
    alarm('renovacion',len(last)==ZERO_RUNS and all(r.get('renewed',0)==0 for r in last),'Renovación sin capítulos renovados en 3 vueltas seguidas',
        'Últimas vueltas: '+', '.join(f'{iso(r["start"])}: {r.get("renewed",0)}' for r in last)+f'. Estado: {status.get("state","?")}.')
    failed=status.get('failed')
    samples=[s for s in memory.get('failed',[]) if now-s[0]<=3*DAY]
    if isinstance(failed,int):samples.append([now,failed])
    memory['failed']=samples[-200:]
    old=[s for s in samples if now-s[0]>=DAY-2*HOUR]
    base=min(old,key=lambda s:abs(now-DAY-s[0]))[1] if old else None
    alarm('fallos',base is not None and failed is not None and failed>base*(1+FAILED_RISE),'Los fallos de renovación suben más de un 5 % en 24 h',
        f'Fallos ahora: {failed}; hace unas 24 h: {base}.')
    size=int(payload.get('indexBytes',0))
    alarm('indice',size>INDEX_LIMIT,'Índice por encima de 1,8 MB',f'indexBytes={size} (límite de aviso {INDEX_LIMIT}; las APK rechazan el índice por encima de 2 MB).')
    links=(read(folder,'link-health.json',{}) or {}).get('last',{});links_age=now-stamp(links.get('checkedAt',-1))
    alarm('enlaces',links_age>LINK_HEALTH_HOURS*HOUR,'Comprobación de enlaces (link_health) parada',f'Última comprobación: {iso(stamp(links.get("checkedAt",-1)))}.')
    worker=(read(folder,'help-status.json',{}) or {}).get('worker',{}) or {};requests=((worker.get('today') or {}).get('requests'))
    if isinstance(requests,int) and requests>0:memory['workerRequestsAt']=now
    memory.setdefault('workerWatchSince',now)
    quiet_since=memory.get('workerRequestsAt',memory['workerWatchSince'])
    alarm('worker',now-quiet_since>WORKER_HOURS*HOUR,'El Worker de ayuda no recibe peticiones desde hace 24 h',
        f'Última vez con peticiones: {iso(memory["workerRequestsAt"]) if "workerRequestsAt" in memory else "nunca vista"}. Hoy: {worker.get("today")}.')
    for name,date in SECRETS.items():
        left=stamp(date+'T00:00:00+00:00')-now
        alarm('secreto-'+name,left<=SECRET_NOTICE,f'El secreto {name} caduca el {date}',
            f'Quedan {max(0,int(left//DAY))} días. Renuévalo y actualiza la fecha en automation/hourly/health_watch.py (SECRETS).')
    # Written by the daily playback probe (branch playback-probe, copied here by health-watch.yml).
    probe=read(folder,'playback-probe.json',{}) or {}
    for family,row in sorted((probe.get('families') or {}).items()):
        alarm('reproduccion-'+family,row.get('failingDays',0)>=2,f'La reproducción de {family} falla 2 días seguidos',
            f'Resultado del probador ({probe.get("checkedAt","?")}): {json.dumps(row,ensure_ascii=False)}')
    return out,memory
class GitHub:
    def __init__(self,repo,token):self.base='https://api.github.com/repos/'+repo;self.token=token
    def call(self,method,path,body=None):
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,method=method,
            headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','User-Agent':'ZZAnime-Vigia/1','Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read() or b'null')
def marker(kind):return f'<!-- vigia:{kind} -->'
def sync(github,results,now):
    """One open issue per failing kind; update on change; close when it passes again."""
    try:github.call('POST','/labels',{'name':LABEL,'color':'d93f0b','description':'Alarmas del vigía de salud'})
    except urllib.error.HTTPError as error:
        if error.code!=422:raise
    open_issues=[]
    for page in range(1,6):
        rows=github.call('GET',f'/issues?state=open&labels={LABEL}&per_page=100&page={page}');open_issues+=rows
        if len(rows)<100:break
    by_kind={}
    for issue in open_issues:
        for kind in results:
            if marker(kind) in (issue.get('body') or ''):by_kind.setdefault(kind,issue)
    actions=[]
    for kind,(failing,title,body) in sorted(results.items()):
        issue=by_kind.get(kind);text=f'{marker(kind)}\n{body}\n\nComprobado: {iso(now)}. Vigía automático, sin IA; se cierra solo cuando se arregla.'
        if failing and not issue:github.call('POST','/issues',{'title':'[Vigía] '+title,'body':text,'labels':[LABEL]});actions.append(('open',kind))
        elif failing and issue and (issue.get('body') or '').split('\n\nComprobado:')[0]!=text.split('\n\nComprobado:')[0]:
            github.call('PATCH',f'/issues/{issue["number"]}',{'title':'[Vigía] '+title,'body':text});actions.append(('update',kind))
        elif not failing and issue:
            github.call('POST',f'/issues/{issue["number"]}/comments',{'body':f'Resuelto: la comprobación vuelve a pasar ({iso(now)}). Cerrada por el vigía.'})
            github.call('PATCH',f'/issues/{issue["number"]}',{'state':'closed','state_reason':'completed'});actions.append(('close',kind))
    return actions
def main():
    a=argparse.ArgumentParser();a.add_argument('--data',required=True);a.add_argument('--memory',required=True);a.add_argument('--dry-run',action='store_true');args=a.parse_args()
    now=datetime.datetime.now(datetime.timezone.utc).timestamp();memory_path=Path(args.memory)
    memory=json.loads(memory_path.read_bytes()) if memory_path.exists() else {}
    results,memory=check(args.data,now,memory)
    memory_path.parent.mkdir(parents=True,exist_ok=True);memory_path.write_text(json.dumps(memory,sort_keys=True),encoding='utf-8')
    failing=sorted(k for k,(f,_,_) in results.items() if f);print(json.dumps({'failing':failing,'checked':len(results),'aiCalls':0}))
    if not args.dry_run:print(json.dumps({'issues':sync(GitHub(os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN']),results,now)}))
if __name__=='__main__':main()
