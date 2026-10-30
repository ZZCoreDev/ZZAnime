import datetime,json,os,unittest
from pathlib import Path
from unittest.mock import patch
from archive_state import save
from renew import continue_if_due
import test_renew

class Response:
    def __init__(self,body=None,status=200):self.body=body or {};self.status=status
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return json.dumps(self.body).encode()

def runs(*rows):return Response({'workflow_runs':list(rows)})
def ago(seconds):return (datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=seconds)).isoformat().replace('+00:00','Z')

class ChainContinuityTests(unittest.TestCase):
    # Two real series from the archive, so the chain is checked with genuine pending work.
    SERIES=['https://jkanime.net/psyren/','https://jkanime.net/dark-summoner-to-dekiteiru/']
    def folder(self,temp,parent,state_name):
        _,_,_,state=test_renew.RenewalTests().fixture()
        url=parent+'4/';state['episodes']={url:next(iter(state['episodes'].values()))};state['listings']={parent:{'complete':True,'observedAt':state['episodes'][url]['observedAt'],'episodes':[parent+str(n)+'/' for n in range(1,5)]}}
        folder=Path(temp);save(folder,state);(folder/'renewal-status.json').write_text(json.dumps({'state':state_name}));return folder
    def call(self,folder,responses,outcome='success'):
        env={'GITHUB_REPOSITORY':'ZZCoreDev/ZZAnime','GH_TOKEN':'test-only','GITHUB_RUN_ID':'7','ZZ_RENEW_OUTCOME':outcome}
        with patch.dict(os.environ,env),patch('renew.urllib.request.urlopen',side_effect=responses) as call,patch('renew.time.sleep') as sleep:continue_if_due(folder)
        return call,sleep
    def test_failed_batch_still_continues_after_spacing(self):
        for parent in self.SERIES:
            with self.subTest(series=parent),test_renew.RenewalTests().temporary() as temp:
                folder=self.folder(temp,parent,'failed')
                call,sleep=self.call(folder,[Response({'run_started_at':ago(60)}),runs(),runs(),Response(status=204)],'failure')
                self.assertEqual(call.call_args_list[-1].args[0].get_method(),'POST')
                self.assertGreater(sleep.call_args.args[0],200);self.assertLessEqual(sleep.call_args.args[0],300)
    def test_long_failed_batch_continues_without_extra_wait(self):
        with test_renew.RenewalTests().temporary() as temp:
            folder=self.folder(temp,self.SERIES[0],'failed')
            call,sleep=self.call(folder,[Response({'run_started_at':ago(780)}),runs(),runs(),Response(status=204)],'failure')
            self.assertEqual(call.call_args_list[-1].args[0].get_method(),'POST');sleep.assert_not_called()
    def test_stale_queued_news_run_does_not_stop_the_chain(self):
        with test_renew.RenewalTests().temporary() as temp:
            folder=self.folder(temp,self.SERIES[1],'complete')
            call,_=self.call(folder,[runs({'status':'queued','created_at':ago(3*86400)}),runs({'status':'queued','created_at':ago(2*86400)}),Response(status=204)])
            self.assertEqual(call.call_args_list[-1].args[0].get_method(),'POST')
    def test_fresh_queued_news_run_keeps_priority(self):
        with test_renew.RenewalTests().temporary() as temp:
            folder=self.folder(temp,self.SERIES[0],'complete')
            call,_=self.call(folder,[runs({'status':'queued','created_at':ago(120)})])
            self.assertEqual(call.call_count,1);self.assertEqual(call.call_args.args[0].get_method(),'GET')
    def test_workflow_continues_unless_cancelled(self):
        here=Path(__file__).resolve().parent
        path=next(p for p in [here.parents[1]/'.github/workflows/provider-renew.yml',here/'renew.yml'] if p.exists())
        text=path.read_text(encoding='utf-8');step=text[text.index('Continuar el histórico pendiente'):]
        self.assertIn("if: ${{ !cancelled() && inputs.proof != true && vars.ZZ_RENEW_ENABLED == 'true' }}",step)
        self.assertIn('ZZ_RENEW_OUTCOME: ${{ job.status }}',step)

if __name__=='__main__':unittest.main()
