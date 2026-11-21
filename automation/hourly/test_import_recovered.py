import contextlib,copy,datetime,gzip,io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from archive_state import load,save
import extra_channel
import import_recovered
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

 def test_pc_refresh_replaces_only_with_a_newer_real_observation(self):
  now,url,batch,state,a=self.fixture();state['episodes'][url]={'observedAt':(now-datetime.timedelta(days=9)).isoformat(),'old':True}
  incoming,held,reused=prepare(batch,state,a,now,replace=True);self.assertIn(url,incoming['episodes']);self.assertEqual(reused,0)
  state['episodes'][url]={'observedAt':(now+datetime.timedelta(minutes=1)).isoformat(),'newer':True}
  incoming,held,reused=prepare(batch,state,a,now,replace=True);self.assertFalse(incoming['episodes']);self.assertEqual(reused,1)
 def test_news_requires_the_confirmed_table_marker(self):
  _,url,batch,state,approved=self.fixture()
  batch['state']['episodes'][url]['pcNews']=True
  with self.assertRaisesRegex(ValueError,'verified server table'):
   import_recovered.split_pc_news(batch,state,approved)

 def test_pc_news_supplement_preserves_primary_and_real_dates(self):
  now=datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=2)
  parent='https://jkanime.net/tsuihou-sareta-tensei-juukishi-wa-game-chishiki-de-musou-suru/'
  url=parent+'21/'
  title='Tsuihou sareta Tensei Juukishi wa Game Chishiki de Musou suru'
  main_link='https://mega.nz/embed/testmega#different'
  links=[
   ('Mega','mega','https://mega.nz/embed/testmega#other'),
   ('Streamwish','streamwish','https://streamwish.com/e/streamwish21'),
   ('Streamtape','streamtape','https://streamtape.com/e/streamtape21'),
   ('Filemoon','filemoon','https://filemoon.sx/e/filemoon21'),
   ('Mixdrop','mixdrop','https://mxdrop.click/e/testmixdrop21'),
  ]
  listing={'series':parent,'title':title,'complete':True,'observedAt':now.isoformat(),'episodes':[url]}
  observed={'episode':url,'observedAt':now.isoformat(),'complete':True,'pcNews':True,'extraction':'embedded-server-table',
            'providers':[{'name':n,'family':f,'links':[link]} for n,f,link in links]}
  root_ep={'episode':url,'complete':True,'observedAt':(now-datetime.timedelta(hours=1)).isoformat(),
           'providers':[{'name':'Mega','family':'mega','links':[main_link]}],
           'extraProviders':[{'name':'YourUpload','family':'yourupload','links':['https://www.yourupload.com/embed/test21']}]}
  batch={'schema':1,'proof':{'allTwoPlayed':True},'state':{'episodes':{url:observed},'listings':{parent:listing}}}
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp)/'state';path=Path(tmp)/'batch.json.gz'
   save(folder,{'episodes':{url:root_ep},'listings':{parent:listing}})
   raw_batch=gzip.compress(run.raw(batch))
   path.write_bytes(raw_batch)
   with patch.dict(os.environ,{'ZZ_DATA':str(folder),'ZZ_PC_BATCH':str(path),'ZZ_IMPORT_SHA256':run.sha(raw_batch)}),contextlib.redirect_stdout(io.StringIO()):
    import_recovered.main(pc=True)
    self.assertEqual(load(folder)['episodes'][url],root_ep)
    supplement=load(folder/extra_channel.JK_NEWS_FOLDER)
    self.assertEqual(supplement['episodes'][url]['observedAt'],observed['observedAt'])
    self.assertEqual([(p['name'],p['links'][0]) for p in supplement['episodes'][url]['providers']],[(n,l) for n,_,l in links])
    self.assertEqual(json.loads((folder/'pc-import-status.json').read_bytes())['supplemented'],1)
    import_recovered.main(pc=True)
    self.assertEqual(json.loads((folder/'pc-import-status.json').read_bytes())['supplemented'],0)
   # Render the real shard structure through the existing signed channel path.
   from cryptography.hazmat.primitives.asymmetric import rsa
   key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
   files=extra_channel.render(folder,datetime.datetime.now(datetime.timezone.utc),key,set())
   shard=json.loads(gzip.decompress(next(v for n,v in files.items() if n.startswith('extra/series/'))))
   self.assertEqual([o['name'] for o in shard['episodes'][0]['extraOptions']],[n for n,_,_ in links])
   self.assertEqual(shard['episodes'][0]['options'],[])
   self.assertEqual(shard['episodes'][0]['observedAt'],observed['observedAt'])
   self.assertTrue(all(o['url']!=main_link for o in shard['episodes'][0]['extraOptions']))

if __name__=='__main__':unittest.main()
