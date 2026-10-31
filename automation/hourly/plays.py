"""Ranking and option scores from device play votes (help Worker /v1/play-stats), without JK.

The ranking counts distinct devices per series over 7 days. Option scores are played/failed device
votes over 14 days, keyed by the first 16 hex characters of sha256(name\\0url); apps order their
options with them. Nothing is removed or added: scores only change the order."""
import json
MAX_RANKING=50
MAX_OPTIONS=2000
def load(folder):
 path=folder/'play-stats.json'
 if not path.exists():return None
 x=json.loads(path.read_bytes())
 return x if isinstance(x.get('options'),list) and isinstance(x.get('popular'),list) else None
def ranking(stats,published,titles):
 items=[{'series':r['series'],'title':titles.get(r['series'],''),'devices':int(r['devices'])} for r in stats['popular'] if isinstance(r,dict) and r.get('series') in published and int(r.get('devices',0))>=2]
 return {'schema':1,'days':7,'basis':'distinct-devices','items':items[:MAX_RANKING]}
def scores(stats):
 def pair(v):return [max(0,int(v[0])),max(0,int(v[1]))]
 options={}
 for r in stats['options'][:MAX_OPTIONS]:
  key=str(r.get('key',''))
  if len(key)==64 and all(c in '0123456789abcdef' for c in key):options[key[:16]]=pair([r.get('ok',0),r.get('fail',0)])
 families={f:pair(v) for f,v in (stats.get('families') or {}).items() if isinstance(f,str) and isinstance(v,list) and len(v)==2}
 return {'schema':1,'days':14,'keyPrefix':16,'families':families,'options':options}
