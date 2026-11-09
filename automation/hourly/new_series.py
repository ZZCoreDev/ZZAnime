"""New JK series missing from the catalogue (9/11/2026: Demons' Crest), verified without JK, which refuses the cloud.
A slug the collector saw on the TioAnime/AnimeFLV home but could not place is accepted only when both detail pages
exist under that same slug with the same exact title, and no catalogue series has that title. Rejected slugs wait
7 days. The collector then reads its chapters from TioAnime/AnimeFLV as for any catalogue series."""
from pathlib import Path
import html,json,re,time,urllib.request,urllib.error
FILE='new-series.json'
LIMIT=3
WAIT=7*86400
UA='ZZAnime-Data/1'

def load(folder):
    path=Path(folder)/FILE
    return json.loads(path.read_bytes()) if path.exists() else {'accepted':{},'rejected':{}}

def rows(folder):
    return [{'url':url,'title':r['title'],'year':None} for url,r in sorted(load(folder)['accepted'].items())]

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:return r.status,r.geturl(),r.read(600000).decode('utf-8','replace')
    except urllib.error.HTTPError as e:return e.code,url,''

def norm(text):return re.sub(r'\s+',' ',html.unescape(text or '')).strip().casefold()

def titles(tio,flv):
    a=re.search(r'<title>\s*(.+?)\s*-\s*TioAnime\s*</title>',tio,re.S|re.I);b=re.search(r'<title>\s*Ver\s+(.+?)\s+Online\s*\S*\s*AnimeFLV\s*</title>',flv,re.S|re.I)
    return (html.unescape(a.group(1)).strip() if a else None),(html.unescape(b.group(1)).strip() if b else None)

def episodes(tio):
    m=re.search(r'var\s+episodes\s*=\s*\[([0-9,\s]*)\]',tio)
    return sorted({int(n) for n in re.findall(r'[0-9]+',m.group(1)) if 0<int(n)<=5000}) if m else []

def verify(folder,slugs,catalogue,now=None,fetcher=fetch,sleep=time.sleep):
    """Returns the chapter URLs of newly accepted series (TioAnime's episode list), for the collector's retry queue."""
    now=now or time.time();folder=Path(folder);data=load(folder);known={r['url'] for r in catalogue};taken={norm(r['title']) for r in catalogue}
    checked=0;chapters=[]
    # Accepted before chapters were queued (9/11/2026): read TioAnime's episode list once.
    for url,r in data['accepted'].items():
        if 'episodes' in r or checked>=LIMIT:continue
        checked+=1;status,final,tio=fetcher(r['tio']);sleep(3)
        if status==200 and final==r['tio']:numbers=episodes(tio);r['episodes']=len(numbers);chapters+=[url+str(n)+'/' for n in numbers]
    for slug in slugs:
        url='https://jkanime.net/'+slug+'/'
        if checked>=LIMIT or not re.fullmatch(r'[a-z0-9-]{2,120}',slug) or url in known or url in data['accepted'] or data['rejected'].get(url,{}).get('retryAt',0)>now:continue
        checked+=1
        tio_url='https://tioanime.com/anime/'+slug;flv_url='https://vww.animeflv.one/anime/'+slug
        s1,u1,tio=fetcher(tio_url);sleep(3);s2,u2,flv=fetcher(flv_url);sleep(3)
        t1,t2=titles(tio,flv)
        if s1!=200 or s2!=200 or u1!=tio_url or u2!=flv_url:reason='source page missing'
        elif not t1 or not t2 or norm(t1)!=norm(t2):reason='titles differ'
        elif norm(t1) in taken:reason='title already in catalogue'
        else:
            numbers=episodes(tio);data['accepted'][url]={'title':t1,'tio':tio_url,'flv':flv_url,'verifiedAt':now,'episodes':len(numbers)};data['rejected'].pop(url,None)
            chapters+=[url+str(n)+'/' for n in numbers];continue
        data['rejected'][url]={'reason':reason,'retryAt':now+WAIT}
    if checked:(folder/FILE).write_text(json.dumps(data,ensure_ascii=False,indent=1,sort_keys=True),encoding='utf-8')
    return chapters
