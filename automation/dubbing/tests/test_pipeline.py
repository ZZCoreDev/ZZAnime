from __future__ import annotations
import copy,datetime,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from dubpipe import ingest,fit,mix,qa,publish,tts,notify
from dubpipe.core import Cache,Episode,read,save
from dubpipe.state import State
from dubpipe.cli import doctor,process,worst_case_gpu_usd

def sample()->Episode:return Episode('sample-1','cc-series','CC test','https://download.blender.org/test.mp4','en',{'authorized':True,'creator':'Test creator','source_url':'https://example.org/source','license':'CC-BY-3.0','license_url':'https://creativecommons.org/licenses/by/3.0/'})
class Tests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def test_ingest_requires_provenance(self):
  row=sample();object.__setattr__(row,'provenance',{})
  with self.assertRaises(ValueError):row.validate()
 def test_ingest_valid_direct_identity(self):sample().validate()
 def test_no_platform_bypass_adapter(self):
  with self.assertRaises(ValueError):ingest.discover({'sources':[{'enabled':True,'kind':'abema_drm_scraper'}]})
 def test_episode_identity_cannot_escape(self):
  row=sample();object.__setattr__(row,'id','../other')
  with self.assertRaises(ValueError):row.validate()
 def test_cache_hits_and_verifies_hashes(self):
  calls=[];cache=Cache(self.root)
  def action(out):calls.append(1);(out/'a.txt').write_text('original');return {'file':'a.txt'}
  folder,_=cache.step('separate',[],{},action);cache.step('separate',[],{},action);self.assertEqual(len(calls),1);(folder/'a.txt').write_text('corrupt');cache.step('separate',[],{},action);self.assertEqual(len(calls),2)
 def test_failed_fit_does_not_repeat_earlier_stages(self):
  cache=Cache(self.root);calls=[]
  def earlier(out):calls.append('separate');(out/'a.txt').write_text('audio');return {'file':'a.txt'}
  a,_=cache.step('separate',[],{},earlier)
  with self.assertRaises(RuntimeError):cache.step('fit',[a/'a.txt'],{},lambda _:(_ for _ in ()).throw(RuntimeError('interrupted')))
  cache.step('separate',[],{},earlier);self.assertEqual(calls,['separate'])
 def test_cache_rejects_outside_artifact(self):
  cache=Cache(self.root);calls=[]
  def action(out):calls.append(1);(out/'a').write_text('x');return {'file':'a'}
  folder,_=cache.step('qa',[],{},action);m=read(folder/'manifest.json');m['artifacts']['../outside']='bad';save(folder/'manifest.json',m);cache.step('qa',[],{},action);self.assertEqual(len(calls),2)
 def test_translation_same_ids_and_count(self):
  from dubpipe.translate import validate
  rows=[{'id':'1','start':0,'end':2,'text':'Hello'}];self.assertEqual(validate(rows,[{'id':'1','es':'Hola'}])[0]['es'],'Hola')
  with self.assertRaises(ValueError):validate(rows,[{'id':'2','es':'Hola'}])
  with self.assertRaises(ValueError):validate(rows,[])
 def test_fit_compression_bound(self):self.assertEqual(fit.duration_ratio(4,3),0.75)
 def test_fit_does_not_stretch_short_phrase(self):self.assertEqual(fit.duration_ratio(2,10),1)
 def test_fit_invalid_window(self):
  with self.assertRaises(ValueError):fit.duration_ratio(2,0)
 def test_srt_millisecond_boundary(self):self.assertEqual(mix.stamp(61.123),'00:01:01,123')
 def test_wer(self):self.assertEqual(qa.wer('Hola, MUNDO.','hola mundo'),0);self.assertEqual(qa.wer('uno dos tres cuatro','uno dos otro cuatro'),0.25)
 def metrics(self):return {'segments':10,'out_of_time_fraction':0,'wer':0,'duration_deviation':0,'clipping_fraction':0,'speech_silence_seconds':0}
 def limits(self):return {'max_out_of_time_fraction':0.05,'max_wer':0.15,'max_duration_deviation':0.03,'max_clipping_fraction':0.0001,'max_speech_silence_seconds':1.5}
 def test_qa_failures_cannot_publish(self):
  m=self.metrics();m['wer']=0.151;self.assertIn('wer',qa.decide(m,self.limits()))
  m=self.metrics();m['out_of_time_fraction']=0.051;self.assertIn('out_of_time_fraction',qa.decide(m,self.limits()))
 def test_no_speech_is_review_not_success(self):
  m=self.metrics();m['segments']=0;self.assertIn('no_speech',qa.decide(m,self.limits()))
 def test_tts_saves_model_provenance(self):
  cfg={'model_cache':str(self.root),'voices':{'es':{'name':'stock','base_url':'https://huggingface.co/example/resolve/main/voice'}}}
  def get(url,target,*args):target.write_bytes(b'model or card')
  with patch('dubpipe.tts.download',side_effect=get):tts.voice_path(cfg)
  self.assertTrue((self.root/'stock.MODEL_CARD.txt').exists())
 def test_publication_preserves_attribution_and_disclosure(self):
  payload=publish.metadata(sample(),'a'*64);self.assertIn('Test creator',payload['snippet']['description']);self.assertIn('CC-BY',payload['snippet']['description']);self.assertTrue(payload['status']['containsSyntheticMedia']);self.assertEqual(payload['status']['privacyStatus'],'private')
 def test_preview_never_contacts_youtube(self):
  with patch('dubpipe.publish.client',side_effect=AssertionError('No API allowed')):result=publish.execute(sample(),{},'a'*64,self.root,{'enabled':False})
  self.assertEqual(result['status'],'preview')
 def test_state_idempotence(self):
  state=State(self.root/'state.json');state.status('sample','uploaded',url='https://youtube.com/watch?v=test');self.assertTrue(state.done('sample'));self.assertEqual(State(state.path).data['episodes']['sample']['url'],'https://youtube.com/watch?v=test')
 def test_daily_budget_reservation(self):
  state=State(self.root/'state.json');state.reserve('one',0.4,0.8);state.reserve('two',0.4,0.8)
  with self.assertRaises(ValueError):state.reserve('three',0.4,0.8)
  self.assertEqual(len(read(state.path)['reservations']),2)
 def test_zero_and_nan_budgets_block(self):
  state=State(self.root/'state.json')
  for amount,cap in [(0.1,0),(float('nan'),1),(0.1,float('inf'))]:
   with self.assertRaises(ValueError):state.reserve('test',amount,cap)
 def test_zero_budget_never_starts_paid_job(self):
  config={'enabled':False,'max_gpu_usd_per_day':0}
  with patch.dict(os.environ,{},clear=True):
   self.assertFalse(doctor(config)['configured'])
   with self.assertRaises(ValueError):process(config,{},self.root,State(self.root/'state.json'))
 def test_stale_price_stops_paid_execution(self):
  with self.assertRaises(ValueError):worst_case_gpu_usd({'gpu_rate_checked':(datetime.datetime.now(datetime.timezone.utc).date()-datetime.timedelta(days=31)).isoformat()})
 def test_notification_without_recipient_is_local_only(self):
  with patch.dict(os.environ,{},clear=True):result=notify.execute({'uploaded':[],'gpu_usd':0},self.root)
  self.assertEqual(result['delivered'],[]);self.assertTrue((self.root/'summary.json').exists())
if __name__=='__main__':unittest.main()
