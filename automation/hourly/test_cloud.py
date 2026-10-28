import unittest,datetime,hashlib
from run import build,record_recent,COLLECTION_BATCHES,RETRY_SECONDS
class CloudTests(unittest.TestCase):
 def test_frequent_collection_is_bounded(self):
  self.assertEqual(COLLECTION_BATCHES,2)
  self.assertEqual(RETRY_SECONDS,900)
  from pathlib import Path
  local=Path(__file__).parent/"hourly.yml"
  target=local if local.exists() else Path(__file__).resolve().parents[2]/".github/workflows/provider-hourly.yml"
  workflow=target.read_text(encoding="utf-8")
  self.assertIn("2-59/5 * * * *",workflow)
  self.assertIn("cancel-in-progress: false",workflow)
 def fixture(self):
  now=datetime.datetime.now(datetime.timezone.utc);parent='https://jkanime.net/test/';url=parent+'1/';link='https://mega.nz/embed/example#key';name='Mega'
  state={'listings':{parent:{'complete':True,'observedAt':now.isoformat(),'episodes':[url]}},'episodes':{url:{'complete':True,'observedAt':now.isoformat(),'providers':[{'name':name,'family':'mega','links':[link]}]}}}
  return now,parent,url,state,{hashlib.sha256((name+'\0'+link).encode()).hexdigest():True}
 def test_valid_observed_episode(self):
  now,parent,url,s,a=self.fixture();index,files=build(s,a,now);self.assertEqual(len(index['series']),1);self.assertEqual(len(files),1)
 def test_existing_homepage_chapter_is_not_lost_by_skip(self):
  now,parent,url,s,a=self.fixture();record_recent(s,[url],now);index,_=build(s,a,now)
  self.assertEqual(len(index['feed']['episodes']),1)
  before=s['newsSeen'][url];record_recent(s,[url],now+datetime.timedelta(hours=1));self.assertEqual(s['newsSeen'][url],before)
 def test_recent_requires_archived_identity_and_listing(self):
  now,parent,url,s,a=self.fixture();record_recent(s,['https://example.com/test/1/',parent+'999/'],now);self.assertEqual(s['newsSeen'],{})
  s['listings'][parent]['episodes']=[];record_recent(s,[url],now);self.assertEqual(s['newsSeen'],{})
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
 def test_renewing_old_episode_does_not_create_a_new_release(self):
  now,_,url,s,a=self.fixture();index,_=build(s,a,now);self.assertEqual(index['feed']['episodes'],[])
  seen=(now-datetime.timedelta(days=2)).isoformat();s['newsSeen']={url:seen};index,_=build(s,a,now)
  self.assertEqual(index['feed']['episodes'][0]['firstSeenAt'],seen)
  self.assertEqual(index['feed']['episodes'][0]['number'],1)
 def test_old_news_not_presented_as_current(self):
  now,_,url,s,a=self.fixture();s['newsSeen']={url:(now-datetime.timedelta(days=8)).isoformat()};index,_=build(s,a,now);self.assertEqual(index['feed']['episodes'],[])
if __name__=='__main__':unittest.main()
