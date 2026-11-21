"""News-only isolation: synthetic sources, no live links, secrets or publication."""
import contextlib,copy,datetime,io,json,os,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
import run
from archive_state import load,save
from voe_channel import split

class ReachedBuild(Exception):pass

class NewsResilienceTests(unittest.TestCase):
 def fixture(self,slug='news-test',voe=False):
  parent='https://jkanime.net/'+slug+'/';url=parent+'1/'
  now=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=1)).isoformat()
  provider={'family':'voe','name':'Voe','links':['https://voe.sx/e/synthetic123']} if voe else {'family':'mp4upload','name':'Mp4upload','links':['https://www.mp4upload.com/embed-synthetic.html']}
  return {'episodes':{url:{'episode':url,'complete':True,'observedAt':now,'providers':[provider]}},'listings':{parent:{'series':parent,'complete':True,'observedAt':now,'episodes':[url]}},'pending':[]},url
 def response(self,state):
  body={'passed':True,'primary':'available','state':state}
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,*args):return json.dumps(body).encode()
  return Response()
 def execute(self,folder,responses,*,proof=False,expect_build=False,request=None):
  with contextlib.ExitStack() as stack:
   stack.enter_context(patch.object(run,'D',Path(folder)))
   build=stack.enter_context(patch.object(run,'build',side_effect=ReachedBuild))
   opener=stack.enter_context(patch('run.NO_REDIRECT.open',side_effect=request or responses))
   stack.enter_context(patch('link_health.check',return_value={'excluded':0}))
   stack.enter_context(patch.dict(os.environ,{'ZZ_COLLECTOR_URL':'https://collector.invalid','ZZ_COLLECTOR_KEY':'synthetic-only','ZZ_HELP_URL':'','ZZ_PROOF':str(proof).lower()}))
   stack.enter_context(patch('sys.argv',['run.py','--collect']+([] if proof else ['--publish'])))
   output=stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
   if expect_build:
    with self.assertRaises(ReachedBuild):run.main()
   else:run.main();build.assert_not_called()
   return opener,output.getvalue()
 def test_bad_voe_never_blocks_valid_providers_or_other_series(self):
  source,url=self.fixture(voe=True);other,other_url=self.fixture('second-series',True)
  source['episodes'].update(other['episodes']);source['listings'].update(other['listings'])
  source['episodes'][url]['providers'][0]['name']='VOE 2'
  source['episodes'][url]['providers'].append(self.fixture()[0]['episodes'][url]['providers'][0])
  original=copy.deepcopy(source)
  with tempfile.TemporaryDirectory() as folder:
   confirmed=set()
   legacy,count=split(folder,source,isolate_invalid=True,confirmed=confirmed)
   self.assertEqual(source,original);self.assertEqual(count,1)
   self.assertEqual(confirmed,{other_url})
   self.assertEqual(legacy['voeScopeRejected'],[url])
   self.assertEqual([p['family'] for p in legacy['episodes'][url]['providers']],['mp4upload'])
   self.assertEqual(set(load(Path(folder)/'voe-state')['episodes']),{other_url})
   evidence=list(Path(folder,'quarantine/news-voe').glob('*.json'));self.assertEqual(len(evidence),1)
   before=evidence[0].read_bytes();source['episodes'][url]['observedAt']=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(milliseconds=500)).isoformat()
   split(folder,source,isolate_invalid=True)
   self.assertEqual(len(list(evidence[0].parent.glob('*.json'))),1);self.assertEqual(evidence[0].read_bytes(),before)
 def test_bad_hosts_paths_queries_credentials_and_labels_are_not_accepted(self):
  for link in ['http://voe.sx/e/id','https://voe.sx.evil/e/id','https://voe.sx/e/id?x=1','https://voe.sx/e/id/','https://user@voe.sx/e/id','https://voe.sx:443/e/id','https://voe.sx/id',None]:
   with self.subTest(link=link),tempfile.TemporaryDirectory() as folder:
    source,url=self.fixture(voe=True);source['episodes'][url]['providers'][0]['links']=[link]
    legacy,count=split(folder,source,isolate_invalid=True)
    self.assertEqual(count,0);self.assertEqual(legacy['episodes'],{});self.assertEqual(load(Path(folder)/'voe-state')['episodes'],{})
    self.assertTrue(list(Path(folder,'quarantine/news-voe').glob('*.json')))
 def test_strict_default_proof_date_and_identity_checks_remain(self):
  for mode in ['scope','date','identity']:
   with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
    source,url=self.fixture(voe=True)
    if mode=='scope':source['episodes'][url]['providers'][0]['name']='VOE 2'
    if mode=='date':source['episodes'][url]['observedAt']='2000-01-01T00:00:00Z'
    if mode=='identity':source['listings'].clear()
    with self.assertRaises(ValueError):split(folder,source,isolate_invalid=mode!='scope')
    self.assertEqual(list(Path(folder).iterdir()),[])
 def test_quarantined_only_chapter_retries_and_keeps_existing_dates(self):
  with tempfile.TemporaryDirectory() as folder:
   original,old=self.fixture('existing');original['newsSeen']={old:original['episodes'][old]['observedAt']};save(folder,original)
   source,url=self.fixture(voe=True);source['episodes'][url]['providers'][0]['name']='VOE 2'
   opener,output=self.execute(folder,[self.response(source),self.response({'episodes':{},'listings':{}})],expect_build=True)
   state=load(folder);self.assertEqual(state['episodes'],original['episodes']);self.assertEqual(state['newsSeen'],original['newsSeen'])
   self.assertEqual(state['pending'],[url]);self.assertEqual(state['voeScopePending'],[url]);self.assertIn(url,state['deferred'])
   self.assertNotIn(url,json.loads(opener.call_args_list[1].args[0].data)['retry'])
   self.assertIn('::warning::',output);self.assertNotIn('voe.sx',output)
   self.assertEqual(json.loads(Path(folder,'collection-status.json').read_bytes())['coverage'],'partial')
 def test_mixed_chapter_scope_retry_overrides_root_skip_then_clears(self):
  for valid in (True,False):
   with self.subTest(regular_option_valid=valid),tempfile.TemporaryDirectory() as folder:
    state,url=self.fixture();state.update(pending=[url],voeScopePending=[url],deferred={url:0});save(folder,state)
    good,_=self.fixture(voe=True);regular=copy.deepcopy(state['episodes'][url]['providers'][0])
    if not valid:regular['links']=['https://provider.invalid/embed-demo.html']
    good['episodes'][url]['providers'].append(regular)
    opener,_=self.execute(folder,[self.response(good),self.response({'episodes':{},'listings':{}})],expect_build=True)
    sent=json.loads(opener.call_args_list[0].args[0].data)
    self.assertIn(url,sent['retry']);self.assertNotIn(url,sent['skip'])
    saved=load(folder);self.assertEqual(saved['pending'],[]);self.assertEqual(saved['voeScopePending'],[])
    self.assertIn(url,load(Path(folder)/'voe-state')['episodes'])
    self.assertEqual(saved['episodes'][url]['providers'],state['episodes'][url]['providers'])
    if not valid:self.assertEqual(saved['episodes'][url],state['episodes'][url])
 def test_first_timeout_retains_prior_state_and_does_not_publish(self):
  for error in [TimeoutError('private source address'),urllib.error.URLError(TimeoutError('private source address'))]:
   with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as folder:
    state,url=self.fixture();state.update(pending=[url],newsSeen={url:state['episodes'][url]['observedAt']});save(folder,state)
    before={p.relative_to(folder):p.read_bytes() for p in Path(folder).rglob('*') if p.is_file()}
    opener,output=self.execute(folder,[error])
    self.assertEqual(opener.call_count,1);self.assertNotIn('private source address',output)
    for p,body in before.items():self.assertEqual(Path(folder,p).read_bytes(),body)
    status=json.loads(Path(folder,'collection-status.json').read_bytes());self.assertEqual(status['state'],'deferred');self.assertEqual(status['completedBatches'],0)
 def test_second_timeout_keeps_first_batch_and_allows_validated_build(self):
  with tempfile.TemporaryDirectory() as folder:
   state,url=self.fixture();opener,_=self.execute(folder,[self.response(state),TimeoutError()],expect_build=True)
   self.assertEqual(opener.call_count,2);self.assertEqual(load(folder)['episodes'],state['episodes'])
   status=json.loads(Path(folder,'collection-status.json').read_bytes());self.assertEqual(status['state'],'deferred');self.assertEqual(status['completedBatches'],1);self.assertEqual(status['collected'],1)
 def test_proof_timeout_http_redirect_auth_and_bad_json_still_fail(self):
  for proof,error in [(True,TimeoutError()),(False,urllib.error.HTTPError('https://collector.invalid',302,'redirect',{},None)),(False,urllib.error.HTTPError('https://collector.invalid',401,'auth',{},None)),(False,urllib.error.URLError('DNS failure')),(False,json.JSONDecodeError('bad','',0))]:
   with self.subTest(proof=proof,error=type(error).__name__),tempfile.TemporaryDirectory() as folder:
    with self.assertRaises(type(error)):self.execute(folder,[error],proof=proof)
 def test_proof_never_quarantines_or_passes_a_rejected_voe(self):
  with tempfile.TemporaryDirectory() as folder:
   source,url=self.fixture(voe=True);source['episodes'][url]['providers'][0]['name']='VOE 2'
   with self.assertRaisesRegex(ValueError,'VOE provider scope'):self.execute(folder,[self.response(source)],proof=True)
   self.assertFalse(Path(folder,'quarantine').exists());self.assertEqual(load(folder)['episodes'],{})
 def test_news_watchdog_respects_deferred_source_and_reports_it_truthfully(self):
  import news_watchdog as watchdog
  with tempfile.TemporaryDirectory() as folder:
   status=Path(folder,'collection-status.json');status.write_text(json.dumps({'state':'checking'}))
   def collect(*args,**kwargs):status.write_text(json.dumps({'state':'deferred','checkedAt':'1970-01-01T00:16:40Z'}))
   with patch.dict(os.environ,{'ZZ_NEWS_WATCHDOG_ENABLED':'true'}),patch.object(watchdog.time,'time',return_value=1000),patch.object(watchdog.subprocess,'run',side_effect=collect) as called:
    self.assertTrue(watchdog.check(folder));self.assertFalse(watchdog.check(folder));self.assertEqual(called.call_count,1)
   report=json.loads(Path(folder,'news-watchdog.json').read_bytes());self.assertEqual(report['state'],'deferred');self.assertEqual(report['retryAt'],1900)
   Path(folder,'news-watchdog.json').unlink()
   self.assertFalse(watchdog.due(folder,1899));self.assertTrue(watchdog.due(folder,1900));self.assertTrue(watchdog.due(folder,999))

if __name__=='__main__':unittest.main()
