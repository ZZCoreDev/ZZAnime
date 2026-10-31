"""Remote switches carried in the signed channel as `config`: app behaviour changes without a new APK.

Only behaviour knobs live here (device help, dead-link reports, a notice for everyone, a minimum
version for apps that read it). Endpoints, keys and every security check stay fixed inside the app.
Each value is checked before signing; an invalid file publishes the channel without `config`."""
from pathlib import Path
import datetime,json,re
W=Path(__file__).resolve().parent
NUMBERS={'deviceHelp':{'tvShare':(0.0,1.0),'mobileShare':(0.0,1.0),'tvPages':(0,200),'mobilePages':(0,100),'renewFraction':(0.0,1.0)},
 'deadReports':{'perDay':(0,100)}}
PLATFORMS={'tv','mobile'}
def section(name,x):
 if not isinstance(x,dict) or set(x)-set(NUMBERS[name])-{'enabled'}:raise ValueError('Remote config '+name)
 out={}
 if 'enabled' in x:
  if not isinstance(x['enabled'],bool):raise ValueError('Remote config '+name+'.enabled')
  out['enabled']=x['enabled']
 for key,(low,high) in NUMBERS[name].items():
  if key not in x:continue
  v=x[key]
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not low<=v<=high or (isinstance(high,int) and not isinstance(v,int)):raise ValueError('Remote config '+name+'.'+key)
  out[key]=v
 return out
def notice(x,now):
 if x is None:return None
 if not isinstance(x,dict) or set(x)-{'id','text','until','platforms'}:raise ValueError('Remote config notice')
 if not isinstance(x.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',x['id']) or not isinstance(x.get('text'),str) or not 0<len(x['text'])<=500:raise ValueError('Remote config notice')
 out={'id':x['id'],'text':x['text']}
 if 'until' in x:
  until=datetime.datetime.fromisoformat(str(x['until']).replace('Z','+00:00'))
  if until.tzinfo is None:raise ValueError('Remote config notice.until')
  if until<now:return None
  out['until']=until.isoformat().replace('+00:00','Z')
 if 'platforms' in x:
  if not isinstance(x['platforms'],list) or not x['platforms'] or set(x['platforms'])-PLATFORMS:raise ValueError('Remote config notice.platforms')
  out['platforms']=sorted(set(x['platforms']))
 return out
def load(now,path=None):
 path=path or W/'remote-config.json'
 if not path.exists():return None
 x=json.loads(path.read_bytes())
 if not isinstance(x,dict) or x.get('schema')!=1 or set(x)-{'schema','version','deviceHelp','deadReports','notice','minVersion'}:raise ValueError('Remote config keys')
 if isinstance(x.get('version'),bool) or not isinstance(x.get('version'),int) or x['version']<1:raise ValueError('Remote config version')
 out={'version':x['version']}
 for name in NUMBERS:
  if name in x:out[name]=section(name,x[name])
 n=notice(x.get('notice'),now)
 if n:out['notice']=n
 if x.get('minVersion') is not None:
  m=x['minVersion']
  if not isinstance(m,dict) or not m or set(m)-PLATFORMS or any(isinstance(v,bool) or not isinstance(v,int) or v<1 for v in m.values()):raise ValueError('Remote config minVersion')
  out['minVersion']=dict(sorted(m.items()))
 return out
