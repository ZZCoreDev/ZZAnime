import copy,datetime,json,tempfile,time,unittest
from pathlib import Path
from archive_state import load
from voe_channel import split,due_targets,PROOF
from run import build,sha

class VoeChannelTests(unittest.TestCase):
 def fixture(self,url):
  parent=url.rsplit('/',2)[0]+'/';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
  return {'episodes':{url:{'episode':url,'observedAt':now,'complete':True,'providers':[{'family':'voe','name':'Voe','links':['https://voe.sx/e/test123']}] }},'listings':{parent:{'series':parent,'title':'Test','complete':True,'observedAt':now,'episodes':[url]}}}
 def test_two_series_isolated_and_idempotent(self):
  for url in PROOF:
   with self.subTest(url=url),tempfile.TemporaryDirectory() as folder:
    source=self.fixture(url);original=copy.deepcopy(source);legacy,count=split(folder,source)
    self.assertEqual(count,1);self.assertEqual(legacy['episodes'],{});self.assertEqual(source,original);self.assertEqual(load(folder)['episodes'],{})
    old=load(Path(folder)/'voe-state')['episodes'][url]['observedAt']
    source['episodes'][url]['observedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    self.assertEqual(split(folder,source)[1],0);self.assertEqual(load(Path(folder)/'voe-state')['episodes'][url]['observedAt'],old)
 def test_mixed_options_preserve_legacy_provider(self):
  source=self.fixture(PROOF[0]);source['episodes'][PROOF[0]]['providers'].insert(0,{'family':'mp4upload','name':'Mp4upload','links':['https://www.mp4upload.com/embed-test.html']})
  with tempfile.TemporaryDirectory() as d:
   legacy,count=split(d,source);self.assertEqual(count,1);self.assertEqual([p['family'] for p in legacy['episodes'][PROOF[0]]['providers']],['mp4upload'])
 def test_untrusted_and_stale_do_not_write(self):
  for changed in ['host','date','identity']:
   with self.subTest(changed=changed),tempfile.TemporaryDirectory() as d:
    source=self.fixture(PROOF[0]);ep=source['episodes'][PROOF[0]]
    if changed=='host':ep['providers'][0]['links']=['https://voe.sx.evil/e/id']
    if changed=='date':ep['observedAt']='2000-01-01T00:00:00Z'
    if changed=='identity':source['listings'].clear()
    with self.assertRaises(ValueError):split(d,source)
    self.assertEqual(list(Path(d).iterdir()),[])
 def test_legacy_render_rejects_voe_even_with_modern_approval(self):
  source=self.fixture(PROOF[0]);key=sha(b'Voe\0https://voe.sx/e/test123');now=datetime.datetime.now(datetime.timezone.utc)
  with self.assertRaises(ValueError):build(source,{key:True},now)
  index,_=build(source,{key:True},now,allow_voe=True);self.assertEqual(len(index['series']),1)
 def test_renewal_is_due_and_bounded(self):
  from archive_state import save
  with tempfile.TemporaryDirectory() as d:
   source=self.fixture(PROOF[0]);source['episodes'][PROOF[0]]['observedAt']=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(days=5.5)).isoformat();save(Path(d)/'voe-state',source)
   self.assertEqual(due_targets(d,{},time.time(),1),[PROOF[0]]);self.assertEqual(due_targets(d,{PROOF[0]:{'retryAt':time.time()+60}},time.time(),1),[])
 def test_pre_upgrade_write_restored_without_freshening_or_losing_voe(self):
  from voe_channel import repair_legacy
  from archive_state import save
  with tempfile.TemporaryDirectory() as d:
   source=self.fixture(PROOF[0]);baseline=copy.deepcopy(source);ep=baseline['episodes'][PROOF[0]];ep['observedAt']=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=2)).isoformat();ep['providers']=[{'family':'mp4upload','name':'Mp4upload','links':['https://www.mp4upload.com/embed-original.html']}];save(Path(d),source)
   self.assertEqual(repair_legacy(d,baseline)['restored'],1);self.assertEqual(load(d)['episodes'][PROOF[0]],ep);self.assertEqual(load(Path(d)/'voe-state')['episodes'][PROOF[0]]['providers'][0]['family'],'voe');self.assertEqual(len(list(Path(d,'quarantine/voe-legacy').glob('*.json'))),1);self.assertEqual(repair_legacy(d,baseline)['restored'],0)

if __name__=='__main__':unittest.main()
