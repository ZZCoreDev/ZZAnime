"""Daily check of the video links in Robin's editor fichas (public catalogue of zzanime-editor).

A link counts as dead only after two consecutive daily checks see it dead (HTTP 404/410 or the provider's own
"deleted / not found" page). One GitHub issue lists the dead links per ficha; it is updated and closed when none are
left. One request per link per day with a pause between requests; no CAPTCHA, video or ad requests; nothing is hidden
or changed automatically."""
import argparse,json,os,re,subprocess,sys,time,urllib.error,urllib.parse,urllib.request
EDITOR='https://zzanime-editor.zzcoredev.workers.dev'
# 9/11/2026: the editor needs a session for /api/titles; the cloud reads with its own key (X-ZZ-Cloud, GitHub secret
# ZZ_EDITOR_CLOUD_KEY, never printed). Only editor_get sends it, never the provider requests. The editor allows
# 30 fichas a minute per account: one every 2.5 s, and a minute's wait if it still says «slow_down».
TITLE_PAUSE=2.5;SLOW_DOWN_WAIT=61;SLOW_DOWN_TRIES=3
UA='Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Mobile Safari/537.36'
MARKERS=('file was deleted','file not found','video not found','file is no longer available','no longer available',
         'has been deleted','video was deleted','file does not exist','the file you were looking for','archivo no encontrado')
TITLE='Enlaces caídos en tus fichas del editor'

def classify(status,body):
    """'dead', 'ok' or 'unknown' from the HTTP status and the first bytes of the page."""
    if status in (404,410):return 'dead'
    if status==200:
        # Visible text only: some providers keep these phrases in data-* attributes or scripts of every page.
        text=re.sub(r'<[^>]*>',' ',re.sub(r'(?is)<(script|style|template)\b.*?</\1>',' ',body)).lower()
        return 'dead' if any(m in text for m in MARKERS) else 'ok'
    return 'unknown'

def fetch(url,timeout=20):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,r.read(200000).decode('utf-8','replace')
    except urllib.error.HTTPError as e:return e.code,''
    except Exception:return 0,''

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**k):return None
NO_REDIRECT=urllib.request.build_opener(_NoRedirect())  # 11/11 auditoría S-05
def editor_get(path,key,timeout=20):
    req=urllib.request.Request(EDITOR+path,headers={'User-Agent':'ZZAnime-Enlaces/1','Accept':'application/json'})
    # 11/11 auditoría S-05: the cloud key never follows a redirect to another host (unredirected header).
    req.add_unredirected_header('X-ZZ-Cloud',key)
    try:
        with NO_REDIRECT.open(req,timeout=timeout) as r:return r.status,r.read(4*1024*1024).decode('utf-8','replace')
    except urllib.error.HTTPError as e:return e.code,e.read(2000).decode('utf-8','replace')
    except Exception:return 0,''

def fichas(get=None,key=None,sleep=time.sleep):
    """Every published ficha with its links. Stops (SystemExit) when any ficha cannot be read: a partial list would
    silently drop links from the memory, and an empty one would report «all fine»."""
    key=os.environ.get('ZZ_EDITOR_CLOUD_KEY','') if key is None else key
    if get is None:
        if not key:raise SystemExit('Falta el secreto ZZ_EDITOR_CLOUD_KEY: sin él el editor no entrega las fichas.')
        get=lambda path:editor_get(path,key)
    status,body=get('/api/catalogue')
    if status!=200:raise SystemExit('Catálogo del editor no disponible: '+str(status))
    out=[];unread=[]
    for n,item in enumerate(json.loads(body).get('items',[])):
        if n:sleep(TITLE_PAUSE)
        for _ in range(SLOW_DOWN_TRIES):
            status,text=get('/api/titles/'+item['id'])
            if status!=429 or 'slow_down' not in text:break
            sleep(SLOW_DOWN_WAIT)
        if status==404:continue  # unpublished between the catalogue and now
        if status!=200:unread.append(f'{item["id"]}: {status} {text[:80]}');continue
        b=json.loads(text).get('body',{})
        links=[o['url'] for ep in b.get('episodes',[]) for o in ep.get('options',[]) if isinstance(o.get('url'),str)]
        out.append({'id':item['id'],'title':b.get('title',''),'links':links})
    if unread:raise SystemExit(f'No se pudieron leer {len(unread)} de {len(out)+len(unread)} fichas del editor (la memoria no se toca):\n'+'\n'.join(unread[:10]))
    return out

def update(memory,results):
    """memory {url: consecutive dead days}; returns confirmed dead urls (>=2 days)."""
    nxt={}
    for url,state in results.items():
        if state=='dead':nxt[url]=memory.get(url,0)+1
        elif state=='unknown' and url in memory:nxt[url]=memory[url]  # keep the count, do not reset on a timeout
    return nxt,{u for u,n in nxt.items() if n>=2}

def report(items,dead):
    lines=[]
    for f in sorted(items,key=lambda x:x['title'].lower()):
        bad=[u for u in f['links'] if u in dead]
        # 11/11 (auditoría S-03): el aviso es público: solo título y servidor, nunca el enlace (está en el editor).
        if bad:lines.append('- **'+f['title']+'** ('+str(len(bad))+' de '+str(len(f['links']))+'): '+', '.join(sorted({urllib.parse.urlsplit(u).hostname or 'enlace' for u in bad})))
    return '\n'.join(lines)

def gh(*args):return subprocess.run(['gh',*args],check=True,capture_output=True,text=True).stdout

def main():
    a=argparse.ArgumentParser();a.add_argument('--memory',required=True);a.add_argument('--pause',type=float,default=2.0);o=a.parse_args()
    try:memory=json.load(open(o.memory,encoding='utf-8'))
    except Exception:memory={}
    items=fichas();results={}
    for f in items:
        for url in f['links']:
            if url in results:continue
            status,body=fetch(url);results[url]=classify(status,body);time.sleep(o.pause)
    memory,dead=update(memory,results)
    json.dump(memory,open(o.memory,'w',encoding='utf-8'),indent=0,sort_keys=True)
    body=report(items,dead)
    found=json.loads(gh('issue','list','--state','open','--search',TITLE+' in:title','--json','number,title'))
    number=next((i['number'] for i in found if i['title']==TITLE),None)
    if body:
        text='La comprobación diaria ha visto estos enlaces caídos dos días seguidos. Cámbialos o quítalos en el editor.\n\n'+body
        if number:gh('issue','edit',str(number),'--body',text)
        else:gh('issue','create','--title',TITLE,'--body',text)
    elif number:gh('issue','close',str(number),'--comment','Todos los enlaces de tus fichas responden de nuevo.')
    print(json.dumps({'fichas':len(items),'links':len(results),'dead':len(dead),'unknown':sum(v=='unknown' for v in results.values())}))

if __name__=='__main__':main()
