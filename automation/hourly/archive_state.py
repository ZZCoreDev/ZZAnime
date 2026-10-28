"""Sharded observed state, shared by news and renewal; never invent observation dates."""
from pathlib import Path
import datetime,gzip,hashlib,json

def stamp(value):
    try:return datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError,AttributeError):return -1

def merge(target,source):
    for url,ep in source.get('episodes',{}).items():
        old=target['episodes'].get(url)
        if old is None or stamp(ep.get('observedAt'))>stamp(old.get('observedAt')):target['episodes'][url]=ep
    for url,row in source.get('listings',{}).items():
        old=target['listings'].get(url)
        if old is None:target['listings'][url]=row
        else:
            newer=row if stamp(row.get('observedAt'))>stamp(old.get('observedAt')) else old
            target['listings'][url]={**newer,'episodes':sorted(set(old['episodes'])|set(row['episodes']))}
    return target

def load(folder):
    path=Path(folder)/'observations.json'
    state=json.loads(path.read_bytes()) if path.exists() else {'schema':1,'episodes':{},'listings':{},'pending':[]}
    for path in sorted((Path(folder)/'series-state').glob('*.json.gz')):
        row=json.loads(gzip.decompress(path.read_bytes()))
        if hashlib.sha256(row['series'].encode()).hexdigest()!=path.name[:-8]:raise ValueError('State identity mismatch')
        merge(state,{'episodes':row['episodes'],'listings':{row['series']:row['listing']}})
    return state

def save(folder,state,parents=None):
    folder=Path(folder);rows={}
    legacy=folder/'observations.json'
    if not (folder/'series-state').exists() or (legacy.exists() and json.loads(legacy.read_bytes()).get('episodes')):parents=None
    for url,ep in state['episodes'].items():
        parent=url.rsplit('/',2)[0]+'/'
        if parents is None or parent in parents:rows.setdefault(parent,{})[url]=ep
    target=folder/'series-state';target.mkdir(parents=True,exist_ok=True)
    for parent,episodes in sorted(rows.items()):
        if parent not in state['listings']:raise ValueError('Missing observed listing')
        row={'schema':1,'series':parent,'listing':state['listings'][parent],'episodes':episodes}
        body=gzip.compress(json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
        path=target/(hashlib.sha256(parent.encode()).hexdigest()+'.json.gz')
        if not path.exists() or path.read_bytes()!=body:
            temporary=path.with_suffix('.tmp');temporary.write_bytes(body);temporary.replace(path)
    metadata={k:v for k,v in state.items() if k not in ('episodes','listings')}
    metadata.update(schema=1,episodes={},listings={})
    path=folder/'observations.json';temporary=folder/'observations.tmp'
    temporary.write_text(json.dumps(metadata,sort_keys=True,separators=(',',':')),encoding='utf-8');temporary.replace(path)

def import_archive(folder,assets):
    state=load(folder);assets=Path(assets);index=json.loads((assets/'index.bin').read_bytes());incoming={'episodes':{},'listings':{}}
    for item in index['series'].values():
        packed=(assets/item['path']).read_bytes()
        if len(packed)!=item['bytes'] or hashlib.sha256(packed).hexdigest()!=item['sha256']:raise ValueError('Archive hash mismatch')
        row=json.loads(gzip.decompress(packed));parent=row['series'];listing={'complete':True,'observedAt':row['listedAt'],'episodes':row['listedEpisodes']}
        incoming['listings'][parent]=listing
        for ep in row['episodes']:
            providers={}
            for option in ep['options']:
                key=(option['family'],option['name']);providers.setdefault(key,[]).append(option['url'])
            incoming['episodes'][ep['url']]={**{k:v for k,v in ep.items() if k!='options'},'complete':True,'providers':[{'family':k[0],'name':k[1],'links':v} for k,v in providers.items()]}
    merge(state,incoming);save(folder,state)
    return {'series':len(state['listings']),'episodes':len(state['episodes']),'datesInvented':False}
