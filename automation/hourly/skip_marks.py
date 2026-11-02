"""Intro/ending marks agreed by devices (help Worker /v1/marks-stats), published in the index as `skipMarks`.

Keys are the chapter path without the host ("serie/5"); values give whole seconds per kind. Only
published chapters, at most MAX_ITEMS of them, most agreed first."""
import json
import signal_policy as policy
HOST='https://jkanime.net/'
MAX_ITEMS=3000
def valid(x):
 """S2: attested network-v2 summary; each mark agreed by at least two independent networks."""
 if not policy.attested(x) or not isinstance(x.get('marks'),list):return False
 for r in x['marks']:
  if not isinstance(r,dict) or not policy.count(r.get('devices')) or not policy.count(r.get('independentNetworks')) or r['devices']!=r['independentNetworks'] or r['independentNetworks']<2:return False
 return True
def load(folder,now=None):
 """Saved summary, or None when missing, unreadable, unattested or (with now) not fresh. Never rewrites the file."""
 path=folder/'marks.json'
 if not path.exists():return None
 try:x=json.loads(path.read_bytes())
 except (ValueError,OSError):return None
 if not valid(x) or now is not None and not policy.fresh(x,now):return None
 return x
def build(stats,available):
 if not valid(stats):return None
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
