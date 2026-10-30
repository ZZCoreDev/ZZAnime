"""VOE-only news (no root-channel record) must be sent back through the source chain, with a backoff."""
import datetime,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import run

URL='https://jkanime.net/tetsuryou-meet-with-tetsudou-musume/4/'

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
 def voe_state(self,folder,observed):
  side=Path(folder,'voe-state');side.mkdir()
  (side/'observations.json').write_text(json.dumps({'schema':1,'episodes':{},'listings':{},'recent':{URL:observed}}),encoding='utf-8')
 def test_voe_only_episode_is_retried_then_backed_off(self):
  with tempfile.TemporaryDirectory() as d:
   observed=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=7)).isoformat().replace('+00:00','Z');self.voe_state(d,observed)
   state={'schema':1,'episodes':{},'listings':{},'pending':[]}
   first=self.collect(d,state)
   self.assertIn(URL,first[0]['retry'],'VOE-only episode sent back through the source chain')
   self.assertNotIn(URL,first[0]['skip'])
   second=self.collect(d,state)
   self.assertIn(URL,second[0]['skip'],'recheck backs off for VOE_RECHECK_SECONDS')
   self.assertNotIn(URL,second[0]['retry'])
   state['voeRecheck'][URL]-=run.VOE_RECHECK_SECONDS
   third=self.collect(d,state)
   self.assertIn(URL,third[0]['retry'],'retried again after the backoff')
 def test_episode_with_root_record_is_not_rechecked(self):
  with tempfile.TemporaryDirectory() as d:
   now=datetime.datetime.now(datetime.timezone.utc);observed=(now-datetime.timedelta(hours=7)).isoformat().replace('+00:00','Z');self.voe_state(d,observed)
   state={'schema':1,'episodes':{URL:{'observedAt':observed,'providers':[{'family':'streamwish','links':['https://streamwish.com/e/x']}]}},'listings':{},'pending':[]}
   requests=self.collect(d,state)
   self.assertNotIn(URL,requests[0]['retry']);self.assertIn(URL,requests[0]['skip']);self.assertEqual(state.get('voeRecheck'),{})
 def test_recheck_is_limited_per_batch(self):
  with tempfile.TemporaryDirectory() as d:
   side=Path(d,'voe-state');side.mkdir();observed=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=7)).isoformat().replace('+00:00','Z')
   urls=['https://jkanime.net/serie-%d/1/'%i for i in range(5)]
   (side/'observations.json').write_text(json.dumps({'schema':1,'episodes':{},'listings':{},'recent':{u:observed for u in urls}}),encoding='utf-8')
   requests=self.collect(d,{'schema':1,'episodes':{},'listings':{},'pending':[]})
   self.assertEqual(len([u for u in requests[0]['retry'] if u in urls]),run.VOE_RECHECK_LIMIT)

if __name__=='__main__':unittest.main()
