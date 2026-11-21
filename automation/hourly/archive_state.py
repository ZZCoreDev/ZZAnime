"""Sharded observed state, shared by news and renewal; never invent observation dates."""
from pathlib import Path, PureWindowsPath
import datetime,gzip,hashlib,io,json,tempfile

MAX_SHARD_BYTES = 32 * 1024 * 1024


def read_shard(source):
    with gzip.GzipFile(fileobj=source,mode='rb') as stream:
        body = stream.read(MAX_SHARD_BYTES + 1)
    if len(body) > MAX_SHARD_BYTES:
        raise ValueError('State shard exceeds its decoded size limit')
    return json.loads(body)


def require_series(series,episodes):
    if not isinstance(series,str) or not all(
        isinstance(url,str) and url.rsplit('/',2)[0]+'/' == series for url in episodes
    ):
        raise ValueError('Observation belongs to another series')


def validate_collected_series(state):
    if not isinstance(state,dict):
        raise ValueError('Missing collector state')
    episodes,listings=state.get('episodes',{}),state.get('listings',{})
    if not isinstance(episodes,dict) or not isinstance(listings,dict):
        raise ValueError('Invalid collector state')
    for series,listing in listings.items():
        if not isinstance(listing,dict) or listing.get('series',series)!=series or not isinstance(listing.get('episodes'),list):
            raise ValueError('Invalid collector listing')
        require_series(series,listing['episodes'])
    for url,episode in episodes.items():
        if not isinstance(url,str) or not isinstance(episode,dict) or episode.get('episode',url)!=url:
            raise ValueError('Invalid collector episode identity')
        parent=url.rsplit('/',2)[0]+'/'
        if parent not in listings or url not in listings[parent]['episodes']:
            raise ValueError('Collector episode is absent from its own listing')


def state_path(folder, name):
    if not isinstance(name, str) or not name:
        raise ValueError('State path must be relative')
    relative = Path(name)
    windows = PureWindowsPath(name)
    if relative.anchor or windows.anchor or '..' in windows.parts or ':' in name:
        raise ValueError('Invalid state path')
    root = Path(folder).resolve()
    candidate = (root / relative).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise ValueError('State path is outside its directory')
    return candidate


def write_state(path, body):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.state-', delete=False) as output:
            temporary = Path(output.name)
            output.write(body)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

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
    path=state_path(folder,'observations.json')
    state=json.loads(path.read_bytes()) if path.exists() else {'schema':1,'episodes':{},'listings':{},'pending':[]}
    target=state_path(folder,'series-state')
    for path in sorted(target.glob('*.json.gz')):
        with state_path(target,path.name).open('rb') as source:
            row=read_shard(source)
        if hashlib.sha256(row['series'].encode()).hexdigest()!=path.name[:-8]:raise ValueError('State identity mismatch')
        require_series(row['series'],row['episodes'])
        require_series(row['series'],row['listing']['episodes'])
        merge(state,{'episodes':row['episodes'],'listings':{row['series']:row['listing']}})
    return state

def save(folder,state,parents=None):
    folder=Path(folder);rows={}
    legacy=state_path(folder,'observations.json')
    target=state_path(folder,'series-state')
    if not target.exists() or (legacy.exists() and json.loads(legacy.read_bytes()).get('episodes')):parents=None
    for url,ep in state['episodes'].items():
        parent=url.rsplit('/',2)[0]+'/'
        if parents is None or parent in parents:rows.setdefault(parent,{})[url]=ep
    target.mkdir(parents=True,exist_ok=True)
    for parent,episodes in sorted(rows.items()):
        if parent not in state['listings']:raise ValueError('Missing observed listing')
        require_series(parent,state['listings'][parent]['episodes'])
        row={'schema':1,'series':parent,'listing':state['listings'][parent],'episodes':episodes}
        body=gzip.compress(json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode(),mtime=0)
        path=state_path(target,hashlib.sha256(parent.encode()).hexdigest()+'.json.gz')
        if not path.exists() or path.read_bytes()!=body:
            write_state(path,body)
    metadata={k:v for k,v in state.items() if k not in ('episodes','listings')}
    metadata.update(schema=1,episodes={},listings={})
    write_state(legacy,json.dumps(metadata,sort_keys=True,separators=(',',':')).encode())

def import_archive(folder,assets):
    state=load(folder);index=json.loads(state_path(assets,'index.bin').read_bytes());incoming={'episodes':{},'listings':{}}
    for item in index['series'].values():
        asset=state_path(assets,item['path'])
        with asset.open('rb') as source:
            packed=source.read(MAX_SHARD_BYTES + 1)
        if len(packed)>MAX_SHARD_BYTES or len(packed)!=item['bytes'] or hashlib.sha256(packed).hexdigest()!=item['sha256']:raise ValueError('Archive size or hash mismatch')
        row=read_shard(io.BytesIO(packed));parent=row['series'];listing={'complete':True,'observedAt':row['listedAt'],'episodes':row['listedEpisodes']}
        require_series(parent,listing['episodes'])
        require_series(parent,(ep['url'] for ep in row['episodes']))
        incoming['listings'][parent]=listing
        for ep in row['episodes']:
            providers={}
            for option in ep['options']:
                key=(option['family'],option['name']);providers.setdefault(key,[]).append(option['url'])
            incoming['episodes'][ep['url']]={**{k:v for k,v in ep.items() if k!='options'},'complete':True,'providers':[{'family':k[0],'name':k[1],'links':v} for k,v in providers.items()]}
    merge(state,incoming);save(folder,state)
    return {'series':len(state['listings']),'episodes':len(state['episodes']),'datesInvented':False}
