"""extraOptions: providers only the app from móvil 92 / TV 116 validates (YourUpload, MixDrop on new hosts).

Published per chapter next to `options`, only when that chapter already has at least one regular option:
apps up to 91/115 ignore the key, but would drop the series for an empty `options`. Same rules as the
source side (backup-rules extra) and the app's option() for these families."""
import re
from urllib.parse import urlsplit
RULES={'yourupload':('YourUpload',('yourupload.com',),r'/embed/[A-Za-z0-9_-]{4,40}'),
 'mixdrop':('MixDrop',('mixdroop.bz','mixdrop.ps','mxdrop.to','mixdrop.top'),r'/e/[A-Za-z0-9]{4,40}')}
MAX=24
def valid(name,family,url):
 rule=RULES.get(family)
 if not rule or not isinstance(name,str) or len(name)>70 or not re.fullmatch(family+r'(?:[\s0-9:()_-].*)?',name.strip().lower()):return False
 try:u=urlsplit(url)
 except ValueError:return False
 host=u.hostname or ''
 return isinstance(url,str) and len(url)<=500 and u.scheme=='https' and not u.username and not u.password and not u.port and not u.query and not u.fragment and any(host==h or host.endswith('.'+h) for h in rule[1]) and re.fullmatch(rule[2],u.path) is not None
def build(ep,dead,seen,sha):
 out=[]
 for p in ep.get('extraProviders',[]):
  for link in p.get('links',[]):
   k=sha((p.get('name','')+'\0'+link).encode())
   if k in seen or k in dead or not valid(p.get('name'),p.get('family'),link):continue
   seen.add(k);out.append({'family':p['family'],'name':p['name'],'url':link})
 return out[:MAX]
