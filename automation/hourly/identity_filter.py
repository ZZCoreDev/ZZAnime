"""Deterministic approval of series identity aliases (C2): same rules as the local filter.py, no AI.

A candidate maps a JK series to TioAnime (required) and optionally AnimeFLV. It is approved only when the
Tio year equals the catalogue year, both sources list exactly the chapters of the JK listing, no source is a
dub, season/variant marks are equal on both sides, FLV uses Tio's slug, the titles have no HTML entity the
collector's heading() leaves undecoded, and no other series already uses that source slug. Anything else
goes to review with its reasons; approved entries are added without "collector" (released after deploy).

Input lines (tab separated, as sent by the local discoverer):
  jk_slug  tio_year  jk_chapters  tio=slug|title|chapters  [flv=slug|title|chapters]
Usage: python3 identity_filter.py candidates.tsv --data <provider-data state> [--write]"""
from pathlib import Path
import argparse,gzip,hashlib,html,json,re,unicodedata
W=Path(__file__).resolve().parent
DUB={'latino','castellano','doblaje','dub','espanol'}
MARK={'2':'s2','ii':'s2','2nd':'s2','second':'s2','3':'s3','iii':'s3','3rd':'s3','third':'s3','4':'s4','iv':'s4','4th':'s4','5':'s5','v':'s5','5th':'s5','zoku':'zoku','next':'next','returns':'returns','kakusei':'kakusei','ova':'extra','ovas':'extra','oav':'extra','special':'extra','specials':'extra','especiales':'extra','especial':'extra','movie':'movie','pelicula':'movie','gekijouban':'movie','mini':'mini','chibi':'mini','picture':'mini','drama':'mini','r2':'s2','s':'s2','lite':'mini','2wei':'s2','3rei':'s3','herz':'herz','drei':'drei','re':'re','do':'do','mi':'mi'}
# tio-rules heading() decodes only these; any other entity in a source h1 breaks the identity check.
DECODED=re.compile(r'&(?:amp|quot|apos|#39);',re.I)
def toks(s):return [t for t in re.split(r'[^a-z0-9]+',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()) if t]
def marks(*texts):return {MARK[t] for x in texts for t in toks(x) if t in MARK}
def decode(s):
    for _ in range(3):s=html.unescape(s)
    return s
def parse(line):
    c=line.rstrip('\r\n').split('\t')
    row={'jk':c[0],'year':int(c[1]),'chapters':int(c[2]),'sources':{}}
    for part in c[3:]:
        name,value=part.split('=',1);slug,title,count=value.split('|')
        row['sources'][name]={'slug':slug,'raw':title,'title':decode(title),'chapters':int(count)}
    return row
def listing_count(data,url):
    path=Path(data)/'series-state'/(hashlib.sha256(url.encode()).hexdigest()+'.json.gz')
    if not path.exists():return None
    row=json.loads(gzip.decompress(path.read_bytes()))
    return len(row['listing']['episodes']) if row.get('series')==url else None
def review(row,catalogue,identities,listed):
    """Reasons a candidate cannot be approved; empty when it can."""
    url='https://jkanime.net/'+row['jk']+'/';item=catalogue.get(url);tio=row['sources'].get('tio');flv=row['sources'].get('flv');why=[]
    if not item:return ['not-in-catalogue']
    if url in identities:why.append('already-mapped')
    if not tio:return why+['no-tio']
    if set(row['sources'])-{'tio','flv'}:why.append('unknown-source')
    if row['year']!=item.get('year'):why.append('year')
    if listed is None or listed!=row['chapters']:why.append('jk-listing')
    for name,src in row['sources'].items():
        if not re.fullmatch(r'[-a-zA-Z0-9_]+',src['slug']):why.append(name+'-slug')
        if src['chapters']!=row['chapters']:why.append(name+'-chapters')
        if DUB&set(toks(src['title'])+toks(src['slug'])):why.append(name+'-dub')
        if re.search(r'&[#a-zA-Z0-9]+;',DECODED.sub('',html.unescape(src['raw']))):why.append(name+'-entity')
        if marks(src['title'],src['slug'].replace('-',' '))!=marks(item['title'],row['jk'].replace('-',' ')):why.append(name+'-marks')
        if any(other!=url and (s:=e.get('sources',{}).get(name)) and s.get('slug')==src['slug'] for other,e in identities.items()):why.append(name+'-slug-taken')
    if flv and flv['slug']!=tio['slug']:why.append('flv-not-tio-slug')
    return why
def entry(row,catalogue):
    url='https://jkanime.net/'+row['jk']+'/'
    return {'title':catalogue[url]['title'],'year':row['year'],'approved':True,'episodes':row['chapters'],'sources':{n:{'slug':s['slug'],'title':s['title']} for n,s in row['sources'].items()}}
def main():
    a=argparse.ArgumentParser();a.add_argument('candidates');a.add_argument('--data',required=True);a.add_argument('--write',action='store_true');args=a.parse_args()
    catalogue={r['url']:r for r in json.loads((W/'catalogue.json').read_bytes())};path=W/'source-identities.json'
    identities=json.loads(path.read_bytes());approved={};held={}
    for line in Path(args.candidates).read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        row=parse(line);url='https://jkanime.net/'+row['jk']+'/'
        why=review(row,catalogue,{**identities,**approved},listing_count(args.data,url))
        if why:held[url]={'reasons':why,'candidate':row}
        else:approved[url]=entry(row,catalogue)
    print(json.dumps({'approved':len(approved),'review':len(held),'reasons':sorted({r for h in held.values() for r in h['reasons']})}))
    for url,h in held.items():print('review',url,','.join(h['reasons']))
    if args.write:
        identities.update(approved)
        path.write_bytes(json.dumps(identities,indent=2,ensure_ascii=False).replace('\n','\r\n').encode())
        (W/'identity-review.json').write_text(json.dumps(held,indent=1,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
if __name__=='__main__':main()
