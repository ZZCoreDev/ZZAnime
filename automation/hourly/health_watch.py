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
# 9/11/2026: the daily-cap reports (quota.mjs) of the channel (series; cloud key X-ZZ-Cloud = secret ZZ_CHANNEL_KEY)
# and of the editor (fichas; its own cloud key = secret ZZ_EDITOR_CLOUD_KEY), keys never printed. A new ban of an
# account or device keeps the «bloqueos» issue open for 24 h; each new one comments.
QUOTA_URL='https://respaldo.zzanime.uk/owner/quota.json'
EDITOR_QUOTA_URL='https://editor.zzanime.uk/api/cloud/quota.json'
# source: (memory key of the last good read, what it counts, label added to each ban)
QUOTA_SOURCES={'canal':('quotaReadAt','series',' (series)'),'editor':('editorQuotaReadAt','fichas',' (fichas del editor)')}
QUOTA_REPORT_HOURS=6;BAN_NOTICE=DAY;BAN_MEMORY=7*DAY
NOTIFY_UPDATES={'bloqueos'}
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
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None
# 11/11 auditoría S-05: authenticated reads never follow a redirect.
NO_REDIRECT=urllib.request.build_opener(_NoRedirect())
def fetch_quota(key,url=QUOTA_URL):
    """A daily-cap report (channel by default), or None when it cannot be read."""
    req=urllib.request.Request(url,headers={'X-ZZ-Cloud':key,'User-Agent':'ZZAnime-Vigia/1','Cache-Control':'no-cache'})
    try:
        with NO_REDIRECT.open(req,timeout=30) as r:return json.loads(r.read())
    except (urllib.error.URLError,OSError,ValueError):return None
def quota_bans(alarm,reports,now,memory):
    """Alarms «informe-tope» (a report unreadable for 6 h) and «bloqueos» (an account or device banned in the last 24 h).
    reports: {source: report dict, or None if unreadable}; sources not checked are left out."""
    memory.setdefault('quotaWatchSince',now);late=[];good={}
    for source,report in reports.items():
        mark=QUOTA_SOURCES[source][0]
        if isinstance(report,dict) and report.get('schema')==1:memory[mark]=now;good[source]=report
        if now-memory.get(mark,memory['quotaWatchSince'])>QUOTA_REPORT_HOURS*HOUR:
            late.append(f'- {source}: última lectura correcta {iso(memory[mark]) if mark in memory else "nunca"}')
    alarm('informe-tope',late,'No se puede leer el informe del tope diario',
        'Sin el informe no se avisa de los bloqueos.\n'+'\n'.join(late))
    if not good:return
    # 11/11 (auditoría S-03): the issue is public: no account id at all; the owner sees it in /owner/quota.json.
    current=set()
    for source,report in good.items():
        tag=QUOTA_SOURCES[source][2]
        current|={f'Cuenta{tag}|{b.get("at","")}' for b in report.get('bans') or []}  # 11/11 S-03: sin identificador (aviso público); la cuenta está en el panel del dueño
        current|={f'Aparato{tag}|{d.get("at","")}' for d in report.get('deviceBans') or []}
    # 11/11 auditoría S-03: old memory keys (with account id prefixes) are dropped.
    labels={kind+c[2] for kind in ('Cuenta','Aparato') for c in QUOTA_SOURCES.values()}
    seen={k:v for k,v in (memory.get('bans') or {}).items() if k.partition('|')[0] in labels}
    for key in current:seen.setdefault(key,now)
    # Forget only what left the report long ago (device bans stay in it for a year and must not count as new again).
    # A source unread this time keeps its known bans (they must not come back as new on the next good read).
    unread=[QUOTA_SOURCES[s][2] for s in reports if s not in good]
    memory['bans']={k:t for k,t in seen.items() if k in current or now-t<=BAN_MEMORY or any(tag in k.split('|',1)[0] for tag in unread)}
    recent=sorted((k for k,t in memory['bans'].items() if now-t<=BAN_NOTICE),key=lambda k:k.split('|',1)[1],reverse=True)
    lines=[f'- {k.split("|",1)[0]} bloqueado el {iso(stamp(k.split("|",1)[1]))}' for k in recent[:40]]
    alarm('bloqueos',recent,'Cuentas o aparatos bloqueados por el tope diario',
        f'Bloqueos nuevos en las últimas 24 h ({len(recent)}):\n'+'\n'.join(lines)
        +'\n\nActivos ahora: '+'; '.join(f'{source}: {len(r.get("bans") or [])} cuentas y {r.get("bannedDevices",0)} aparatos (tope {r.get("cap","?")} {QUOTA_SOURCES[source][1]} al día)' for source,r in good.items())
        +'. Las cuentas quedan bloqueadas en Supabase; los aparatos, un año. El aviso se cierra solo 24 h después del último bloqueo.')
# 10/11 (REVISION-2 N1): Workers Free gives 100,000 requests a day to all ZZAnime servers together (refused ones count
# too); usually ~10,600. Over USAGE_WARN today means someone may be draining it: «consumo» issue so Robin knows.
USAGE_WARN=50000
CF_ACCOUNT='3407d07c06229321d34863cf0fdac02d'
def cloudflare_usage(token,day,fetch=None):
    """Today's Worker requests per server (dict) or None. Reads Cloudflare's analytics with the cloud's own token."""
    q='{viewer{accounts(filter:{accountTag:"%s"}){workersInvocationsAdaptive(limit:50,filter:{date:"%s"}){sum{requests} dimensions{scriptName}}}}}'%(CF_ACCOUNT,day)
    try:
        if fetch:data=fetch(q)
        else:
            req=urllib.request.Request('https://api.cloudflare.com/client/v4/graphql',data=json.dumps({'query':q}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','User-Agent':'ZZAnime-Vigia/1'})
            with urllib.request.urlopen(req,timeout=30) as r:data=json.loads(r.read())
        rows=data['data']['viewer']['accounts'][0]['workersInvocationsAdaptive'];out={}
        for row in rows:out[row['dimensions']['scriptName']]=out.get(row['dimensions']['scriptName'],0)+int(row['sum']['requests'])
        return out
    except Exception:return None
def check(folder,now,memory,quota=False,editor_quota=False,usage=None):
    """{kind: (failing, title, body)} and the updated memory. quota / editor_quota (channel / editor daily-cap reports):
    report dict, None if unreadable, False if not checked."""
    out={};memory=dict(memory or {})
    def alarm(kind,failing,title,body=''):out[kind]=(bool(failing),title,body)
    reports={s:r for s,r in (('canal',quota),('editor',editor_quota)) if r is not False}
    if reports:quota_bans(alarm,reports,now,memory)
    if usage is not None:
        total=sum(usage.values())
        alarm('consumo',total>USAGE_WARN,'Consumo de Cloudflare muy alto hoy',f'Hoy van {total} peticiones de 100.000 gratuitas (lo normal son unas 11.000). Si se agotan, hasta las 00:00 UTC la app no recibe fichas ni enlaces nuevos. Por servidor: '+', '.join(f'{k}: {v}' for k,v in sorted(usage.items(),key=lambda x:-x[1]))+'.')
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
    alarm('renovacion',len(last)==ZERO_RUNS and all(r.get('renewed',0)+r.get('extraRenewed',0)+r.get('voeRenewed',0)==0 for r in last),'Renovación sin capítulos renovados en 3 vueltas seguidas',
        'Últimas vueltas: '+', '.join(f'{iso(r["start"])}: {r.get("renewed",0)+r.get("extraRenewed",0)+r.get("voeRenewed",0)}' for r in last)+f'. Estado: {status.get("state","?")}.')
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
            f'Resultado del probador ({probe.get("checkedAt","?")}): '+json.dumps({k:v for k,v in row.items() if isinstance(v,(int,float,bool))},ensure_ascii=False))  # S-03: solo números, nunca enlaces
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
            # Editing an issue sends no mail: kinds that are news (a new ban) also comment.
            if kind in NOTIFY_UPDATES:github.call('POST',f'/issues/{issue["number"]}/comments',{'body':body})
        elif not failing and issue:
            github.call('POST',f'/issues/{issue["number"]}/comments',{'body':f'Resuelto: la comprobación vuelve a pasar ({iso(now)}). Cerrada por el vigía.'})
            github.call('PATCH',f'/issues/{issue["number"]}',{'state':'closed','state_reason':'completed'});actions.append(('close',kind))
    return actions
def main():
    a=argparse.ArgumentParser();a.add_argument('--data',required=True);a.add_argument('--memory',required=True);a.add_argument('--dry-run',action='store_true');args=a.parse_args()
    now=datetime.datetime.now(datetime.timezone.utc).timestamp();memory_path=Path(args.memory)
    memory=json.loads(memory_path.read_bytes()) if memory_path.exists() else {}
    key=os.environ.get('ZZ_CHANNEL_KEY','')
    editor_key=os.environ.get('ZZ_EDITOR_CLOUD_KEY','')
    cf=os.environ.get('CLOUDFLARE_API_TOKEN','');usage=cloudflare_usage(cf,datetime.datetime.fromtimestamp(now,datetime.timezone.utc).strftime('%Y-%m-%d')) if cf else None
    results,memory=check(args.data,now,memory,fetch_quota(key) if key else False,fetch_quota(editor_key,EDITOR_QUOTA_URL) if editor_key else False,usage)
    memory_path.parent.mkdir(parents=True,exist_ok=True);memory_path.write_text(json.dumps(memory,sort_keys=True),encoding='utf-8')
    failing=sorted(k for k,(f,_,_) in results.items() if f);print(json.dumps({'failing':failing,'checked':len(results),'aiCalls':0}))
    if not args.dry_run:print(json.dumps({'issues':sync(GitHub(os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN']),results,now)}))
if __name__=='__main__':main()
