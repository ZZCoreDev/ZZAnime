"""Intro/ending marks agreed by devices (help Worker /v1/marks-stats), published in the index as `skipMarks`.

Keys are the chapter path without the host ("serie/5"); values give whole seconds per kind. Only
published chapters, at most MAX_ITEMS of them, most agreed first."""
import json
HOST='https://jkanime.net/'
MAX_ITEMS=3000
def load(folder):
 path=folder/'marks.json'
 if not path.exists():return None
 x=json.loads(path.read_bytes())
 return x if isinstance(x.get('marks'),list) else None
def build(stats,available):
 items={}
 for r in stats['marks']:
  if not isinstance(r,dict):continue
  url,kind=r.get('episode'),r.get('kind')
  if url not in available or kind not in ('intro','outro') or not str(url).startswith(HOST):continue
  start,stop=int(r.get('start',-1)),int(r.get('stop',-1))
  if not 0<=start<stop<=start+240:continue
  key=url[len(HOST):].rstrip('/')
  if key not in items and len(items)>=MAX_ITEMS:continue
  items.setdefault(key,{})[kind]=[start,stop]
 return {'schema':1,'unit':'seconds','items':items}
