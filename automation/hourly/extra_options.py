"""extraOptions: providers only the app from móvil 92 / TV 116 validates (YourUpload, MixDrop on new hosts).

Published per chapter next to `options`, only when that chapter already has at least one regular option:
apps up to 91/115 ignore the key, but would drop the series for an empty `options`. Same rules as the
source side (backup-rules extra) and the app's option() for these families."""
import re
from urllib.parse import urlsplit
RULES={'yourupload':('YourUpload',('yourupload.com',),r'/embed/[A-Za-z0-9_-]{4,40}'),
 'mixdrop':('MixDrop',('mixdrop.ps','mxdrop.to','mixdrop.top'),r'/e/[A-Za-z0-9]{4,40}')}
MAX=24
# mixdroop.bz is a parked domain posing as MixDrop (31/10/2026: its loader redirects to ww1.mixdroop.bz/?subid1=… and
# survey-twist.com; the same ids on real MixDrop read «We can't find the video»). Its links are never valid.
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
def prune(ep):
 """The chapter without extra links that are no longer valid (e.g. mixdroop.bz); same object if nothing changes."""
 rest=[]
 for p in ep.get('extraProviders',[]):
  links=[l for l in p.get('links',[]) if valid(p.get('name'),p.get('family'),l)]
  if links:rest.append({**p,'links':links})
 return ep if rest==ep.get('extraProviders',[]) else {**ep,'extraProviders':rest}
