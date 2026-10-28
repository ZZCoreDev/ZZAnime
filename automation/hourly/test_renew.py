import base64,copy,datetime,gzip,json,os,tempfile,unittest,urllib.error
from unittest.mock import patch
from pathlib import Path
from archive_state import load,save,merge,stamp
from renew import select,validate,status_document,github_status,continue_if_due,record_failure,repair_retry_deadlines,repair_verified_identities,health_report,DAY

class RenewalTests(unittest.TestCase):
    def test_identity_fix_retries_only_affected_old_records_once(self):
        now,_,_,original=self.fixture();old=copy.deepcopy(next(iter(original['episodes'].values())));fresh=copy.deepcopy(old);fresh['observedAt']=now.isoformat();mao='https://jkanime.net/mao/';state={'episodes':{mao+'1/':old,mao+'2/':fresh,'https://jkanime.net/other/1/':old},'listings':{}};failed={url:{'retryAt':now.timestamp()+3600} for url in state['episodes']};dates=copy.deepcopy(state['episodes'])
        identity={mao:{'title':'Mao','year':2026,'approved':True,'sources':{}}};catalog=[{'url':mao,'title':'Mao','year':2026}]
        def read(path):return json.dumps(identity if path.name=='source-identities.json' else catalog).encode()
        with patch.object(Path,'read_bytes',read):
            self.assertEqual(repair_verified_identities(state,failed,now.timestamp()),1);self.assertEqual(failed[mao+'1/']['retryAt'],now.timestamp());self.assertGreater(failed[mao+'2/']['retryAt'],now.timestamp());self.assertGreater(failed['https://jkanime.net/other/1/']['retryAt'],now.timestamp());self.assertEqual(repair_verified_identities(state,failed,now.timestamp()+60),0)
        self.assertEqual(state['episodes'],dates)
    def test_queued_sample_is_not_replaced_by_a_continuation(self):
        class Response:
            def __init__(self,rows):self.rows=rows
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps({'workflow_runs':self.rows}).encode()
        _,_,_,state=self.fixture()
        with self.temporary() as temp:
            folder=Path(temp);save(folder,state);(folder/'renewal-status.json').write_text(json.dumps({'state':'complete'}))
            with patch.dict(os.environ,{'GITHUB_REPOSITORY':'ZZCoreDev/ZZAnime','GH_TOKEN':'test-only'}),patch('renew.urllib.request.urlopen',side_effect=[Response([]),Response([{'status':'pending'}])]) as call:continue_if_due(folder)
            self.assertEqual(call.call_count,2);self.assertTrue(all(r.args[0].get_method()=='GET' for r in call.call_args_list))
    def test_expired_retry_is_not_postponed_forever(self):
        now,_,url,state=self.fixture(8);failed={url:{'retryAt':now.timestamp()+900}}
        self.assertEqual(repair_retry_deadlines(state,failed,now.timestamp()),0)
        self.assertEqual(select(state,failed,now.timestamp()+901,2),[url])
    def test_health_measures_wall_time_and_excludes_proof(self):
        now,_,_,state=self.fixture();instant=now.timestamp()
        with self.temporary() as temp:
            folder=Path(temp);status={'runId':'proof','checkedAt':now.isoformat(),'proof':True,'published':True,'renewed':2}
            h=health_report(folder,state,{},status,instant);self.assertEqual(h['successfulCyclesMeasured'],0);self.assertEqual(h['capacityStatus'],'insufficient-history');self.assertIsNone(h['estimatedSweepDays'])
            for i in range(3):
                started=datetime.datetime.fromtimestamp(instant-7200+i*1200,datetime.timezone.utc).isoformat()
                h=health_report(folder,state,{},dict(status,runId=str(i),checkedAt=started,proof=False,renewed=100),instant)
            self.assertEqual(h['successfulCyclesMeasured'],3);self.assertEqual(h['measuredWallClockPerHour'],150)
            self.assertTrue((folder/'renewal-health.json').exists())
    def test_retries_never_jump_beyond_expiry(self):
        now,_,url,state=self.fixture(6.9);failed={url:{'attempts':30}}
        record_failure(failed,url,'Source unavailable',now.timestamp(),state['episodes'][url]['observedAt'])
        self.assertLess(failed[url]['retryAt'],stamp(state['episodes'][url]['observedAt'])+7*DAY)
        self.assertGreater(failed[url]['retryAt'],now.timestamp())
    def test_legacy_retry_repaired_without_changing_source_dates(self):
        now,_,url,state=self.fixture(2);original=copy.deepcopy(state);old=now.timestamp()+7*DAY;failed={url:{'retryAt':old}}
        self.assertEqual(repair_retry_deadlines(state,failed,now.timestamp()),1);self.assertEqual(state,original)
        self.assertEqual(failed[url]['previousRetryAt'],old);self.assertLessEqual(failed[url]['retryAt'],now.timestamp()+3600)
        self.assertEqual(repair_retry_deadlines(state,failed,now.timestamp()),0)
    def test_repeated_failures_do_not_starve_unchecked_chapters(self):
        now,parent,url,state=self.fixture();failed={}
        for n in range(1,17):
            address=parent+str(n)+'/';state['episodes'][address]=copy.deepcopy(state['episodes'][url]);state['listings'][parent]['episodes'].append(address)
            if n<9:failed[address]={'retryAt':0}
        chosen=select(state,failed,now.timestamp(),8)
        self.assertEqual(len(chosen),8);self.assertEqual(sum(u in failed for u in chosen),2)
    def test_partial_pair_saves_success_and_marks_only_missing(self):
        import renew,run
        now,parent,url,state=self.fixture();second='https://jkanime.net/dark-summoner-to-dekiteiru/4/';state['episodes'][second]=copy.deepcopy(state['episodes'][url]);state['listings'][second.rsplit('/',2)[0]+'/']={'complete':True,'observedAt':state['episodes'][url]['observedAt'],'episodes':[second]}
        incoming=copy.deepcopy(self.fixture(0)[3]);link=incoming['episodes'][url]['providers'][0]['links'][0];key=run.sha(('Mp4upload\0'+link).encode())
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return json.dumps({'passed':True,'state':incoming,'errors':{second:'Episode not found'}}).encode()
        with self.temporary() as temp:
            save(temp,state)
            with patch.dict(os.environ,{'ZZ_DATA':str(temp),'ZZ_COLLECTOR_URL':'https://collector.invalid/','ZZ_COLLECTOR_KEY':'test-only'}),patch('sys.argv',['renew.py','--proof']),patch('renew.urllib.request.urlopen',return_value=Response()),patch('run.compile_java',return_value='test'),patch('run.command',return_value=json.dumps({'key':key,'approved':True})):
                with self.assertRaisesRegex(ValueError,'Two-series renewal proof failed'):renew.main()
            saved=load(temp);self.assertEqual(saved['episodes'][url]['observedAt'],incoming['episodes'][url]['observedAt']);self.assertEqual(saved['episodes'][second]['observedAt'],state['episodes'][second]['observedAt'])
            failures=json.loads((Path(temp)/'renewal-failures.json').read_bytes());self.assertEqual(set(failures),{second});self.assertEqual(failures[second]['reason'],'Episode not found')
    def test_pending_news_is_never_replaced_by_renewal_continuation(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps({'workflow_runs':[{'status':'pending'}]}).encode()
        _,_,_,state=self.fixture()
        with self.temporary() as temp:
            folder=Path(temp);save(folder,state);(folder/'renewal-status.json').write_text(json.dumps({'state':'complete'}))
            with patch.dict(os.environ,{'GITHUB_REPOSITORY':'ZZCoreDev/ZZAnime','GH_TOKEN':'test-only'}),patch('renew.urllib.request.urlopen',return_value=Response()) as call:
                continue_if_due(folder)
            self.assertEqual(call.call_count,1)
            self.assertIn('provider-hourly.yml/runs',call.call_args.args[0].full_url)
    def fixture(self,age=2):
        now=datetime.datetime.now(datetime.timezone.utc);parent='https://jkanime.net/psyren/';url=parent+'4/';observed=(now-datetime.timedelta(days=age)).isoformat()
        return now,parent,url,{'schema':1,'episodes':{url:{'complete':True,'observedAt':observed,'providers':[{'family':'mp4upload','name':'Mp4upload','links':['https://www.mp4upload.com/embed-test.html']}]}},'listings':{parent:{'complete':True,'observedAt':observed,'episodes':[parent+str(n)+'/' for n in range(1,5)]}},'pending':[]}
    def temporary(self):
        path=Path(__file__).parent/'test-runtime';path.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=path)
    def test_select_before_seven_days(self):
        now,_,url,state=self.fixture(2);self.assertEqual(select(state,{},now.timestamp(),2),[url])
    def test_fresh_not_repeated(self):
        now,_,_,state=self.fixture(0);self.assertEqual(select(state,{},now.timestamp(),2),[])
    def test_failure_backoff(self):
        now,_,url,state=self.fixture();self.assertEqual(select(state,{url:{'retryAt':now.timestamp()+900}},now.timestamp(),2),[])
    def test_old_observation_cannot_be_renewed_by_timestamp_only(self):
        now,_,url,state=self.fixture()
        with self.assertRaises(ValueError):validate(state,[url],now.timestamp(),now.timestamp())
    def test_fresh_observation_requires_observed_identity(self):
        now,parent,url,state=self.fixture(0);validate(state,[url],now.timestamp(),now.timestamp())
        state['listings'][parent]['episodes']=[]
        with self.assertRaises(ValueError):validate(state,[url],now.timestamp(),now.timestamp())
    def test_no_unrequested_episode(self):
        now,_,_,state=self.fixture(0)
        with self.assertRaises(ValueError):validate(state,[],now.timestamp(),now.timestamp())
    def test_sharded_roundtrip_keeps_dates_and_listed_chapters(self):
        _,parent,url,state=self.fixture();original=copy.deepcopy(state)
        with self.temporary() as path:
            save(path,state);loaded=load(path);self.assertEqual(loaded,state)
            file=next((Path(path)/'series-state').glob('*.gz'));first=file.read_bytes();save(path,loaded);self.assertEqual(file.read_bytes(),first)
            self.assertEqual(len(loaded['listings'][parent]['episodes']),4);self.assertEqual(loaded['episodes'][url]['observedAt'],original['episodes'][url]['observedAt'])
    def test_newest_wins_and_old_chapters_not_lost(self):
        _,parent,url,old=self.fixture(2);_,_,_,fresh=self.fixture(0)
        fresh['listings'][parent]['episodes']=[url];merge(old,fresh);merge(old,self.fixture(3)[3]);self.assertEqual(old['episodes'][url]['observedAt'],fresh['episodes'][url]['observedAt']);self.assertEqual(len(old['listings'][parent]['episodes']),4)
    def test_failure_report_is_idempotent_and_keeps_manual_notes(self):
        with self.temporary() as temp:
            p=Path(temp)/'ESTADO.md';p.write_text('Notas manuales\n');s={'state':'failed','failed':2,'expired':1};status_document(p,s);first=p.read_bytes();status_document(p,s);self.assertEqual(first,p.read_bytes());self.assertIn('Deuda:',p.read_text());self.assertTrue(p.read_text().startswith('Notas manuales'))
    def test_corrupt_shard_rejected(self):
        _,_,_,state=self.fixture()
        with self.temporary() as temp:
            save(temp,state);p=next((Path(temp)/'series-state').glob('*.gz'));row=json.loads(gzip.decompress(p.read_bytes()));row['series']='https://jkanime.net/other/';p.write_bytes(gzip.compress(json.dumps(row).encode()))
            with self.assertRaises(ValueError):load(temp)
    def test_status_retry_preserves_concurrent_manual_change(self):
        class Response:
            def __init__(self,value):self.body=json.dumps(value).encode()
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,*args):return self.body
        a={'sha':'old','content':base64.b64encode(b'Notas originales\n').decode()};b={'sha':'new','content':base64.b64encode(b'Notas originales\nCambio concurrente\n').decode()}
        calls=[]
        def request(req,**kwargs):
            calls.append(req)
            if len(calls)==1:return Response(a)
            if len(calls)==2:raise urllib.error.HTTPError(req.full_url,409,'conflict',None,None)
            if len(calls)==3:return Response(b)
            payload=json.loads(req.data);self.assertEqual(payload['sha'],'new');self.assertIn('Cambio concurrente',base64.b64decode(payload['content']).decode());return Response({})
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'ZZCoreDev/ZZAnime','GH_TOKEN':'test-only'}),patch('renew.urllib.request.urlopen',side_effect=request),patch('renew.time.sleep'):
            github_status({'state':'failed','failed':1,'expired':0})
        self.assertEqual(len(calls),4)

if __name__=='__main__':unittest.main()
