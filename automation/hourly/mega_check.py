"""MEGA links from AnimeFLV (review list) and TioAnime are published only after MEGA's API reads them alive.

A link counts as alive only when the API returns the file size and attributes ("s" and "at"); -9, -16,
-6 (login page) and any error keep it out. A few checks per run with a pause, newest chapters first;
the answer is cached so each link is asked again only when it gets old."""
import json,time
from pathlib import Path
from archive_state import stamp
import link_health
ALIVE_FOR=3*86400
RETRY_AFTER=6*3600
def sha(b):return link_health.sha(b)
def candidates(state):
 out={}
 for url,ep in sorted(state['episodes'].items(),key=lambda r:stamp(r[1].get('observedAt')),reverse=True):
  source=ep.get('sourceSeries','')
  pool=ep.get('reviewProviders',[]) if source.startswith('https://vww.animeflv.one/') else ep.get('providers',[]) if source.startswith('https://tioanime.com/') else []
  for p in pool:
   if p.get('family')!='mega':continue
   for link in p.get('links',[]):out.setdefault(sha((p['name']+'\0'+link).encode()),(p['name'],link))
 return out
def load(folder):
 path=Path(folder)/'mega-check.json'
 return json.loads(path.read_bytes()) if path.exists() else {}
def check(folder,state,now=None,limit=12,pause=2.5,fetcher=link_health.fetch,sleep=time.sleep):
 now=time.time() if now is None else now;rules=link_health.policy();data=load(folder);found=candidates(state);sent=0;summary={'checked':0,'alive':0,'rejected':0}
 for key,(name,link) in found.items():
  if sent>=limit:break
  old=data.get(key,{})
  if now-old.get('checkedAt',0)<(ALIVE_FOR if old.get('state')=='alive' else RETRY_AFTER):continue
  target=link_health.target('mega',link,rules)
  if not target:continue
  if sent:sleep(pause)
  sent+=1
  try:status,body=fetcher(target)
  except Exception:status,body=None,''
  state_='alive' if link_health.classify('mega',status,body)=='alive' else 'rejected'
  data[key]={'state':state_,'checkedAt':now,'status':status};summary['checked']+=1;summary[state_]+=1
 # Forget answers for links that are no longer stored anywhere.
 data={k:v for k,v in data.items() if k in found}
 (Path(folder)/'mega-check.json').write_text(json.dumps(data,sort_keys=True,separators=(',',':')),encoding='utf-8')
 summary.update(candidates=len(found),aliveKnown=sum(1 for v in data.values() if v['state']=='alive'))
 return summary
def alive(folder,now=None):
 now=time.time() if now is None else now
 return {k for k,v in load(folder).items() if v.get('state')=='alive' and now-v.get('checkedAt',0)<=ALIVE_FOR}
