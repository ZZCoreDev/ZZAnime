"""VOE-only news (seen in the last 7 days, no root-channel record) are sent back through the source chain with a backoff."""
import datetime,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import run

URL='https://jkanime.net/tetsuryou-meet-with-tetsudou-musume/4/'

def iso(delta):return (datetime.datetime.now(datetime.timezone.utc)-delta).isoformat().replace('+00:00','Z')

class VoeRecheckTests(unittest.TestCase):
 def collect(self,folder,state):
  requests=[]
  result={'passed':True,'primary':'unavailable','errors':{},'diagnostics':{},'recent':[],'state':{'episodes':{},'listings':{},'pending':[]}}
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,*args):return json.dumps(result).encode()
  def urlopen(request,timeout=None):requests.append(json.loads(request.data));return Response()
  with patch.object(run,'D',Path(folder)),patch.object(run,'load_observations',return_value=state),patch.object(run,'save_observations'),patch.object(run,'compile_java') as build,patch('urllib.request.urlopen',side_effect=urlopen),patch.dict(os.environ,{'ZZ_COLLECTOR_URL':'https://collector.invalid','ZZ_COLLECTOR_KEY':'test-only'}),patch('sys.argv',['run.py','--news-only','--collect','--publish']):run.main()
  build.assert_not_called()
  return requests
 def voe_recent(self,folder,urls):
  side=Path(folder,'voe-state');side.mkdir()
  (side/'observations.json').write_text(json.dumps({'schema':1,'episodes':{},'listings':{},'recent':{u:iso(datetime.timedelta(hours=1)) for u in urls}}),encoding='utf-8')
 def test_voe_only_news_is_retried_then_backed_off(self):
  with tempfile.TemporaryDirectory() as d:
   self.voe_recent(d,[URL])
   state={'schema':1,'episodes':{},'listings':{},'pending':[],'newsSeen':{URL:iso(datetime.timedelta(hours=14))}}
   first=self.collect(d,state)
   self.assertIn(URL,first[0]['retry'],'VOE-only news sent back through the source chain')
   self.assertNotIn(URL,first[0]['skip'])
   second=self.collect(d,state)
   self.assertIn(URL,second[0]['skip'],'recheck backs off for VOE_RECHECK_SECONDS')
   self.assertNotIn(URL,second[0]['retry'])
   state['voeRecheck'][URL]-=run.VOE_RECHECK_SECONDS
   third=self.collect(d,state)
   self.assertIn(URL,third[0]['retry'],'retried again after the backoff')
 def test_news_dropped_from_short_voe_recent_list_is_still_retried(self):
  # Real case 2026-10-30: Watashi 29 fell out of the 500-entry VOE recent list filled by renewals.
  with tempfile.TemporaryDirectory() as d:
   history=['https://jkanime.net/ao-ashi/%d/'%n for n in range(2,25)];self.voe_recent(d,history)
   state={'schema':1,'episodes':{},'listings':{},'pending':[],'newsSeen':{URL:iso(datetime.timedelta(hours=27))}}
   requests=self.collect(d,state)
   self.assertIn(URL,requests[0]['retry'])
   self.assertFalse(set(history)&set(requests[0]['retry']),'historical VOE-only episodes are left to renewal')
   self.assertTrue(set(history)<=set(requests[0]['skip']))
 def test_news_with_root_record_or_older_than_seven_days_is_not_rechecked(self):
  with tempfile.TemporaryDirectory() as d:
   old='https://jkanime.net/old-series/3/';self.voe_recent(d,[])
   state={'schema':1,'episodes':{URL:{'observedAt':iso(datetime.timedelta(hours=1)),'providers':[{'family':'streamwish','links':['https://streamwish.com/e/x']}]}},'listings':{},'pending':[],'newsSeen':{URL:iso(datetime.timedelta(hours=7)),old:iso(datetime.timedelta(days=8))}}
   requests=self.collect(d,state)
   self.assertNotIn(URL,requests[0]['retry']);self.assertNotIn(old,requests[0]['retry']);self.assertEqual(state.get('voeRecheck'),{})
 def test_recheck_is_limited_per_batch(self):
  with tempfile.TemporaryDirectory() as d:
   self.voe_recent(d,[]);urls=['https://jkanime.net/serie-%d/1/'%i for i in range(5)]
   requests=self.collect(d,{'schema':1,'episodes':{},'listings':{},'pending':[],'newsSeen':{u:iso(datetime.timedelta(hours=3)) for u in urls}})
   self.assertEqual(len([u for u in requests[0]['retry'] if u in urls]),run.VOE_RECHECK_LIMIT)

if __name__=='__main__':unittest.main()
