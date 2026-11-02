"""Ranking and option scores from device play votes (help Worker /v1/play-stats), without JK.

The ranking counts distinct devices per series over 7 days. Option scores are played/failed device
votes over 14 days, keyed by the first 16 hex characters of sha256(name\\0url); apps order their
options with them. Nothing is removed or added: scores only change the order."""
import json
import signal_policy as policy
MAX_RANKING=50
MAX_OPTIONS=2000
def valid(x):
 """S2: attested network-v2 summary whose counts are whole, consistent numbers (one verdict per network)."""
 if not policy.attested(x) or not isinstance(x.get('options'),list) or not isinstance(x.get('popular'),list) or not isinstance(x.get('families'),dict):return False
 totals={}
 for r in x['options']:
  if not isinstance(r,dict) or not all(policy.count(r.get(k)) for k in ('ok','fail','independentNetworks')) or r['ok']+r['fail']!=r['independentNetworks']:return False
  if isinstance(r.get('family'),str):t=totals.setdefault(r['family'],[0,0]);t[0]+=r['ok'];t[1]+=r['fail']
 for f,v in x['families'].items():
  if not isinstance(f,str) or not isinstance(v,list) or len(v)!=2 or not all(policy.count(n) for n in v):return False
 for f,(ok,fail) in totals.items():
  v=x['families'].get(f)
  if v is None or v[0]<ok or v[1]<fail:return False
 for r in x['popular']:
  if not isinstance(r,dict) or not isinstance(r.get('series'),str) or not policy.count(r.get('devices')) or not policy.count(r.get('independentNetworks')) or r['devices']!=r['independentNetworks']:return False
 return True
def load(folder,now=None):
 """Saved summary, or None when missing, unreadable, unattested or (with now) not fresh. Never rewrites the file."""
 path=folder/'play-stats.json'
 if not path.exists():return None
 try:x=json.loads(path.read_bytes())
 except (ValueError,OSError):return None
 if not valid(x) or now is not None and not policy.fresh(x,now):return None
 return x
def ranking(stats,published,titles):
 if not valid(stats):return None
 items=[{'series':r['series'],'title':titles.get(r['series'],''),'devices':r['independentNetworks']} for r in stats['popular'] if r['series'] in published and r['independentNetworks']>=2]
 return {'schema':1,'days':7,'basis':policy.BASIS,'items':items[:MAX_RANKING]}
def scores(stats):
 if not valid(stats):return None
 def pair(v):return [max(0,int(v[0])),max(0,int(v[1]))]
 options={}
 for r in stats['options'][:MAX_OPTIONS]:
  key=str(r.get('key',''))
  if len(key)==64 and all(c in '0123456789abcdef' for c in key):options[key[:16]]=pair([r.get('ok',0),r.get('fail',0)])
 families={f:pair(v) for f,v in (stats.get('families') or {}).items() if isinstance(f,str) and isinstance(v,list) and len(v)==2}
 return {'schema':1,'days':14,'keyPrefix':16,'families':families,'options':options}
