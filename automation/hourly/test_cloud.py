import unittest,datetime,hashlib
from run import build
class CloudTests(unittest.TestCase):
 def fixture(self):
  now=datetime.datetime.now(datetime.timezone.utc);parent='https://jkanime.net/test/';url=parent+'1/';link='https://mega.nz/embed/example#key';name='Mega'
  state={'listings':{parent:{'complete':True,'observedAt':now.isoformat(),'episodes':[url]}},'episodes':{url:{'complete':True,'observedAt':now.isoformat(),'providers':[{'name':name,'family':'mega','links':[link]}]}}}
  return now,parent,url,state,{hashlib.sha256((name+'\0'+link).encode()).hexdigest():True}
 def test_valid_observed_episode(self):
  now,parent,url,s,a=self.fixture();index,files=build(s,a,now);self.assertEqual(len(index['series']),1);self.assertEqual(len(files),1)
 def test_unapproved_excluded(self):
  now,_,_,s,_=self.fixture()
  with self.assertRaises(ValueError):build(s,{},now)
 def test_unlisted_excluded(self):
  now,parent,_,s,a=self.fixture();s['listings'][parent]['episodes']=[]
  with self.assertRaises(ValueError):build(s,a,now)
 def test_old_excluded(self):
  now,_,url,s,a=self.fixture();s['episodes'][url]['observedAt']=(now-datetime.timedelta(days=8)).isoformat()
  with self.assertRaises(ValueError):build(s,a,now)
 def test_future_excluded(self):
  now,_,url,s,a=self.fixture();s['episodes'][url]['observedAt']=(now+datetime.timedelta(hours=1)).isoformat()
  with self.assertRaises(ValueError):build(s,a,now)
 def test_same_content_reusable(self):
  now,_,_,s,a=self.fixture();one=build(s,a,now);two=build(s,a,now);self.assertEqual(one,two)
 def test_android_legacy_utc_format(self):
  now,_,_,s,a=self.fixture();index,_=build(s,a,now);self.assertTrue(index['createdAt'].endswith('Z'));self.assertNotIn('+00:00',index['createdAt'])
if __name__=='__main__':unittest.main()
