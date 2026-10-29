import datetime,unittest
from renew import select
class PrefixTests(unittest.TestCase):
 def fixture(self):
  now=datetime.datetime.now(datetime.timezone.utc);parent='https://jkanime.net/test/';date=(now-datetime.timedelta(days=3)).isoformat();state={'episodes':{},'listings':{parent:{'episodes':[]}}};failures={}
  for n in range(1,401):
   url=parent+str(n)+'/';state['listings'][parent]['episodes'].append(url)
   if n<=300:state['episodes'][url]={'observedAt':date,'complete':True,'providers':[{'links':['https://www.mp4upload.com/embed-test.html']}]}
   if 201<=n<=300:failures[url]={'retryAt':0}
  return now.timestamp(),state,failures
 def test_short_prefix_includes_failed_and_missing_without_duplicates(self):
  now,state,failures=self.fixture();chosen=select(state,failures,now,400,include_missing=True);first=chosen[:8]
  self.assertEqual(len(chosen),len(set(chosen)));self.assertEqual(sum(u in failures for u in first),1);self.assertEqual(sum(u not in state['episodes'] for u in first),1);self.assertEqual(sum(u in state['episodes'] and u not in failures for u in first),6)
 def test_recent_saved_and_backoff_are_never_requeried(self):
  now,state,failures=self.fixture();url='https://jkanime.net/test/1/';state['episodes'][url]['observedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat();paused='https://jkanime.net/test/201/';failures[paused]['retryAt']=now+3600;chosen=select(state,failures,now,100,include_missing=True);self.assertNotIn(url,chosen);self.assertNotIn(paused,chosen)
if __name__=='__main__':unittest.main()
