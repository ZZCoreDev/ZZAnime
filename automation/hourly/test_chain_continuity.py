import datetime,json,os,unittest
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch
from archive_state import save
from renew import continuation_due
import test_renew

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT/'.github/workflows/provider-renew.yml').read_text(encoding='utf-8')
DISPATCH = {}
exec(compile(dedent(WORKFLOW.split('        shell: python\n        run: |\n',1)[1]),'provider-renew.yml:dispatch','exec'),DISPATCH)

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
        self.assertTrue(continuation_due(folder,outcome!='success'))
        with patch.dict(os.environ,env),patch.object(DISPATCH['opener'],'open',side_effect=responses) as call,patch('time.sleep') as sleep:
            DISPATCH['dispatch']()
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
    def test_queued_sample_keeps_its_place(self):
        with test_renew.RenewalTests().temporary() as temp:
            folder=self.folder(temp,self.SERIES[0],'complete')
            call,_=self.call(folder,[runs(),runs({'id':8,'status':'pending','created_at':ago(120)})])
            self.assertEqual([args.args[0].get_method() for args in call.call_args_list],['GET','GET'])
    def test_dispatcher_defers_only_while_another_run_is_processing(self):
        with test_renew.RenewalTests().temporary() as temp:
            folder=self.folder(temp,self.SERIES[0],'complete')
            active=runs({'id':7,'status':'in_progress','created_at':ago(120)},{'id':8,'status':'in_progress','created_at':ago(120)})
            for status in ('in_progress','completed'):
                with self.subTest(status=status):
                    job=Response({'jobs':[{'name':'renew','status':status}]})
                    call,_=self.call(folder,[runs(),active,job,Response(status=204)])
                    self.assertIn('runs/8/jobs',call.call_args_list[2].args[0].full_url)
                    self.assertEqual(call.call_args.args[0].get_method(),'GET' if status=='in_progress' else 'POST')
    def test_news_first_when_it_has_not_run_for_15_minutes(self):
        # 14/11: GitHub drops schedules; the chain dispatches news when it is 15 minutes old, renewal otherwise
        with test_renew.RenewalTests().temporary() as temp:
            folder=self.folder(temp,self.SERIES[0],'complete')
            call,_=self.call(folder,[runs({'status':'completed','created_at':ago(20*60)}),runs(),Response(status=204)])
            self.assertIn('provider-hourly.yml/dispatches',call.call_args.args[0].full_url)
            call,_=self.call(folder,[runs({'status':'completed','created_at':ago(5*60)}),runs(),Response(status=204)])
            self.assertIn('provider-renew.yml/dispatches',call.call_args.args[0].full_url)
    def test_workflow_continues_unless_cancelled(self):
        plan,dispatch=WORKFLOW.split('\n  dispatch:\n',1)
        step=plan[plan.index('Detectar renovación pendiente'):]
        self.assertIn("if: ${{ !cancelled() && inputs.proof != true && vars.ZZ_RENEW_ENABLED == 'true' }}",step)
        self.assertIn('ZZ_RENEW_OUTCOME: ${{ job.status }}',step)
        self.assertIn('actions: read',plan)
        self.assertNotIn('actions: write',plan)
        self.assertIn('actions: write',dispatch)
        self.assertIn("!cancelled() && needs.renew.outputs.continuation_due == 'true'",dispatch)
        self.assertIn('ZZ_RENEW_OUTCOME: ${{ needs.renew.result }}',dispatch)
        for forbidden in ('secrets.', 'actions/checkout', 'ZZ_DATA', 'working-directory:'):
            self.assertNotIn(forbidden,dispatch)

if __name__=='__main__':unittest.main()
