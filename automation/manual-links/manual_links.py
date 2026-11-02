"""Daily check of the video links in Robin's editor fichas (public catalogue of zzanime-editor).

A link counts as dead only after two consecutive daily checks see it dead (HTTP 404/410 or the provider's own
"deleted / not found" page). One GitHub issue lists the dead links per ficha; it is updated and closed when none are
left. One request per link per day with a pause between requests; no CAPTCHA, video or ad requests; nothing is hidden
or changed automatically."""
import argparse,json,re,subprocess,sys,time,urllib.error,urllib.request
EDITOR='https://zzanime-editor.zzcoredev.workers.dev'
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

def fichas(get=fetch):
    status,body=get(EDITOR+'/api/catalogue')
    if status!=200:raise SystemExit('Catálogo del editor no disponible: '+str(status))
    out=[]
    for item in json.loads(body).get('items',[]):
        status,body=get(EDITOR+'/api/titles/'+item['id'])
        if status!=200:continue
        b=json.loads(body).get('body',{})
        links=[o['url'] for ep in b.get('episodes',[]) for o in ep.get('options',[]) if isinstance(o.get('url'),str)]
        out.append({'id':item['id'],'title':b.get('title',''),'links':links})
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
        if bad:lines.append('- **'+f['title']+'** ('+str(len(bad))+' de '+str(len(f['links']))+'):\n'+'\n'.join('  - '+u for u in bad))
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
