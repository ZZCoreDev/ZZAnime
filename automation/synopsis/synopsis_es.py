"""Spanish synopses for catalogue series that have none (Robin, 31/10 and 2/11/2026).

Only series with a strict JK↔AniList identity (anilist-map.json: exact unique alias plus format, year and studio or
episode count) are used. AniList gives the English description; Workers AI translates it, inside the free daily
allowance (a local neuron estimate stops well before it). Every text keeps its origin (anilist id, source hash, model,
date, provenance ai-translated). Resumable and incremental: translated series are never asked again, failures are
recorded with their reason and retried on another day. The app shows a manual correction or JK's own synopsis first.
Usage: synopsis_es.py --state STATE.json [--limit N]
"""
import argparse,datetime,hashlib,html,json,os,re,time,urllib.error,urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
ACCOUNT='3407d07c06229321d34863cf0fdac02d'
MODEL='@cf/meta/llama-3.3-70b-instruct-fp8-fast'
# Workers AI price list for this model, in neurons per million tokens; the free allowance is 10,000 neurons a day.
NEURONS_IN,NEURONS_OUT,DAILY_BUDGET=26668,204805,7000
ANILIST='https://graphql.anilist.co'
QUERY='query($ids:[Int]){Page(perPage:50){media(id_in:$ids,type:ANIME){id description(asHtml:false)}}}'
PROMPT=('Traduce al español de España la sinopsis de anime que te dará el usuario. Devuelve solo la traducción, '
        'sin títulos, comillas, notas ni frases añadidas. Conserva los nombres propios tal cual.')
ES=re.compile(r'\b(el|la|los|las|que|de|en|y|una|un|con|por|su|se|del)\b',re.I)
EN=re.compile(r'\b(the|and|with|his|her|their|who|is|of|to|when|after|into|from)\b',re.I)

def iso(t):return t.astimezone(datetime.timezone.utc).isoformat().replace('+00:00','Z')
def clean(text):
    """AniList markup out: line breaks, tags, entities and the trailing «(Source: …)» credit."""
    text=re.sub(r'<br\s*/?>','\n',text or '',flags=re.I);text=re.sub(r'<[^>]+>','',text);text=html.unescape(text)
    text=re.sub(r'\n?\s*[\(\[]\s*(Source|Fuente|Written by)[^\)\]]*[\)\]]\s*$','',text.strip(),flags=re.I)
    text=re.sub(r'[ \t]+',' ',text);text=re.sub(r'\n{3,}','\n\n',text).strip()
    return text[:1600]
def tokens(text):return max(1,len(text)//4)
def cost(source,translated):return tokens(PROMPT+source)*NEURONS_IN/1e6+tokens(translated or source)*1.3*NEURONS_OUT/1e6
def valid(source,text):
    """A translation is kept only if it looks like the whole text, in Spanish, with nothing added in front."""
    if not text or len(text)<40:return 'empty'
    if not 0.6<=len(text)/max(1,len(source))<=1.8:return 'length'
    if re.match(r'\s*(aquí|claro|here|sure|traducci)',text,re.I):return 'preamble'
    if len(ES.findall(text))<=len(EN.findall(text)):return 'not-spanish'
    return ''

def post(url,body,headers,opener=urllib.request.urlopen):
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'ZZAnime-Synopsis/1',**headers})
    with opener(req,timeout=60) as r:return json.loads(r.read(2_000_000))

def anilist(ids,fetch=None):
    """Descriptions by AniList id, 50 per request, with a pause between requests (AniList allows 90 a minute)."""
    out={}
    for i in range(0,len(ids),50):
        chunk=ids[i:i+50]
        for attempt in range(3):
            try:
                data=fetch(chunk) if fetch else post(ANILIST,{'query':QUERY,'variables':{'ids':chunk}},{})
                for m in data.get('data',{}).get('Page',{}).get('media',[]) or []:out[m['id']]=m.get('description') or ''
                break
            except urllib.error.HTTPError as error:
                if error.code!=429 or attempt==2:raise
                time.sleep(min(90,int(error.headers.get('Retry-After') or 60)))
        if not fetch:time.sleep(2)
    return out

def translate(text,token,run=None):
    if run:return run(text)
    data=post(f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/{MODEL}',
              {'messages':[{'role':'system','content':PROMPT},{'role':'user','content':text}],'max_tokens':900,'temperature':0.2},
              {'Authorization':'Bearer '+token})
    if not data.get('success',True):raise RuntimeError('workers-ai: '+json.dumps(data.get('errors'))[:200])
    return str((data.get('result') or {}).get('response') or '').strip().strip('"«»').strip()

def run(state_path,limit,now=None,fetch=None,ai=None,token=''):
    now=now or datetime.datetime.now(datetime.timezone.utc);day=now.date().isoformat()
    mapping=json.loads((HERE/'anilist-map.json').read_text(encoding='utf-8'))['items']
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    state.setdefault('schema',1);items=state.setdefault('items',{});failed=state.setdefault('failed',{})
    budget=state.get('budget') if (state.get('budget') or {}).get('day')==day else {'day':day,'neurons':0.0}
    todo=[m for m in mapping if m['url'] not in items and (failed.get(m['url']) or {}).get('day')!=day][:limit]
    report={'checkedAt':iso(now),'asked':len(todo),'translated':0,'failed':0,'noDescription':0,'stoppedByBudget':False}
    texts=anilist([m['anilistId'] for m in todo],fetch) if todo else {}
    for m in todo:
        source=clean(texts.get(m['anilistId'],''))
        if len(source)<40:failed[m['url']]={'day':day,'reason':'no-anilist-description'};report['noDescription']+=1;continue
        if budget['neurons']+cost(source,None)>DAILY_BUDGET:report['stoppedByBudget']=True;break
        try:text=translate(source,token,ai)
        except Exception as error:failed[m['url']]={'day':day,'reason':'ai-error: '+str(error)[:120]};report['failed']+=1;continue
        budget['neurons']=round(budget['neurons']+cost(source,text),2)
        why=valid(source,text)
        if why:failed[m['url']]={'day':day,'reason':'rejected-'+why};report['failed']+=1;continue
        items[m['url']]={'text':text,'source':'anilist','anilistId':m['anilistId'],'sourceSha256':hashlib.sha256(source.encode()).hexdigest(),
                         'model':MODEL,'provenance':'ai-translated','translatedAt':iso(now),'identity':m.get('method','')}
        failed.pop(m['url'],None);report['translated']+=1
    state['budget']=budget;state['updatedAt']=iso(now);state['total']=len(items);state['last']=report
    state_path.write_text(json.dumps(state,ensure_ascii=False,sort_keys=True,indent=0),encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',required=True);p.add_argument('--limit',type=int,default=150);a=p.parse_args()
    token=os.environ.get('CLOUDFLARE_API_TOKEN','')
    if not token:raise SystemExit('CLOUDFLARE_API_TOKEN missing')
    print(json.dumps(run(Path(a.state),max(0,min(a.limit,300)),token=token)),flush=True)
