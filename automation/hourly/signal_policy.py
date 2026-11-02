"""S2: rules every device summary (play votes, intro/ending marks) must meet before it can change the signed index.

The help Worker counts independent networks (one /24 or /48 = one voter) and only devices older than 24 h.
Older or unknown summaries, stale or future ones, incomplete ones and inconsistent counts are ignored: they
never remove anything, they just stop moving rankings, option order or skip marks."""
import datetime
POLICY='network-v2'
BASIS='independent-networks'
MAX_COUNT=2**53
def count(v):return isinstance(v,int) and not isinstance(v,bool) and 0<=v<MAX_COUNT
def generated(x):
 v=x.get('generatedAt') if isinstance(x,dict) else None
 if not isinstance(v,str) or 'T' not in v:return None
 try:t=datetime.datetime.fromisoformat(v.replace('Z','+00:00'))
 except ValueError:return None
 return t if t.tzinfo else None
def attested(x):
 return isinstance(x,dict) and x.get('evidencePolicy')==POLICY and x.get('basis')==BASIS and x.get('complete') is True and count(x.get('minDeviceAgeHours')) and x['minDeviceAgeHours']>=24 and generated(x) is not None
def fresh(x,now):
 t=generated(x)
 return t is not None and now-datetime.timedelta(days=1)<=t<=now+datetime.timedelta(minutes=5)
