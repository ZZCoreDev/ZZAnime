"""Weekly schedule derived from when each chapter first appeared in the news, without any JK request.

Each series keeps its latest chapter seen in the last `days`, placed on the weekday and time (Madrid)
it appeared. Only chapters that have options in the channel are listed."""
import datetime
from zoneinfo import ZoneInfo
MADRID=ZoneInfo('Europe/Madrid')
def iso(t):return t.astimezone(datetime.timezone.utc).isoformat().replace('+00:00','Z')
def build(state,available,now,titles,days=8):
 latest={}
 for url,seen in state.get('newsSeen',{}).items():
  if url not in available:continue
  try:t=datetime.datetime.fromisoformat(str(seen).replace('Z','+00:00'))
  except ValueError:continue
  if t.tzinfo is None or not 0<=(now-t).total_seconds()<=days*86400:continue
  parent=url.rsplit('/',2)[0]+'/'
  if parent not in latest or t>latest[parent][0]:latest[parent]=(t,url)
 items=[]
 for parent,(t,url) in latest.items():
  local=t.astimezone(MADRID)
  items.append({'series':parent,'title':titles.get(parent,''),'weekday':local.isoweekday(),'time':local.strftime('%H:%M'),'episode':int(url.rstrip('/').rsplit('/',1)[1]),'url':url,'seenAt':iso(t)})
 items.sort(key=lambda x:(x['weekday'],x['time'],x['title'],x['series']))
 return {'schema':1,'timezone':'Europe/Madrid','basis':'first-seen','days':days,'items':items[:300]}
