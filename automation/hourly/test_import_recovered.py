import copy,datetime,tempfile,unittest
from pathlib import Path
from import_recovered import prepare
import run

class ImportTests(unittest.TestCase):
 def fixture(self):
  now=datetime.datetime.now(datetime.timezone.utc);parent='https://jkanime.net/vivy-fluorite-eyes-song/';url=parent+'1/';link='https://www.mp4upload.com/embed-test.html'
  ep={'archiveVersion':3,'episode':url,'observedAt':now.isoformat(),'complete':True,'providers':[{'name':'Mp4upload','family':'mp4upload','links':[link]}]}
  source={'episodes':{url:ep},'listings':{parent:{'series':parent,'title':"Vivy: Fluorite Eye's Song",'complete':True,'observedAt':now.isoformat(),'episodes':[url]}}}
  return now,url,{'schema':1,'proof':{'allTwoPlayed':True},'state':source},{'episodes':{},'listings':{}},{run.sha(('Mp4upload\0'+link).encode()):True}
 def test_two_sample_gate(self):
  now,_,batch,state,a=self.fixture();batch['proof']['allTwoPlayed']=False
  with self.assertRaises(ValueError):prepare(batch,state,a,now)
 def test_import_keeps_real_date(self):
  now,url,batch,state,a=self.fixture();incoming,held,reused=prepare(batch,state,a,now);self.assertEqual(incoming['episodes'][url]['observedAt'],batch['state']['episodes'][url]['observedAt']);self.assertFalse(held);self.assertEqual(reused,0);self.assertEqual(state['episodes'],{})
 def test_existing_episode_never_replaced(self):
  now,url,batch,state,a=self.fixture();state['episodes'][url]={'observedAt':'2020-01-01T00:00:00Z','untouched':True};before=copy.deepcopy(state);incoming,held,reused=prepare(batch,state,a,now);self.assertFalse(incoming['episodes']);self.assertEqual(reused,1);self.assertEqual(state,before)
 def test_missing_listing_rejected(self):
  now,_,batch,state,a=self.fixture();batch['state']['listings']={}
  with self.assertRaises(ValueError):prepare(batch,state,a,now)
 def test_wrong_season_rejected(self):
  now,url,batch,state,a=self.fixture();batch['state']['listings'][url.rsplit('/',2)[0]+'/']['title']='Vivy Season 2'
  with self.assertRaises(ValueError):prepare(batch,state,a,now)
 def test_stale_dates_not_renewed(self):
  now,url,batch,state,a=self.fixture();batch['state']['episodes'][url]['observedAt']=(now-datetime.timedelta(days=8)).isoformat();incoming,held,_=prepare(batch,state,a,now);self.assertFalse(incoming['episodes']);self.assertIn(url,held)
 def test_unapproved_provider_held(self):
  now,url,batch,state,_=self.fixture();incoming,held,_=prepare(batch,state,{},now);self.assertFalse(incoming['episodes']);self.assertIn(url,held)
 def test_unobserved_number_rejected(self):
  now,url,batch,state,a=self.fixture();batch['state']['episodes'][url]['episode']=url.replace('/1/','/2/')
  with self.assertRaises(ValueError):prepare(batch,state,a,now)

if __name__=='__main__':unittest.main()
