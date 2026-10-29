import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import run

class EmptyNewsTests(unittest.TestCase):
 def test_two_series_empty_check_retains_dates_and_does_not_build_or_publish(self):
  for slug in ['psyren','dark-summoner-to-dekiteiru']:
   with self.subTest(slug=slug),tempfile.TemporaryDirectory() as d:
    parent='https://jkanime.net/'+slug+'/';url=parent+'4/'
    state={'episodes':{url:{'observedAt':'2026-10-29T00:00:00Z','providers':[]}},'listings':{parent:{'episodes':[url]}},'newsSeen':{url:'2026-10-29T00:00:00Z'},'pending':[]};original=copy.deepcopy(state)
    result={'passed':True,'primary':'unavailable','errors':{parent+'5/':'Source HTTP 403'},'diagnostics':{},'recent':[url],'state':{'episodes':{},'listings':{},'pending':[]}}
    class Response:
     def __enter__(self):return self
     def __exit__(self,*args):pass
     def read(self,*args):return json.dumps(result).encode()
    with patch.object(run,'D',Path(d)),patch.object(run,'load_observations',return_value=state),patch.object(run,'save_observations'),patch.object(run,'compile_java') as build,patch('urllib.request.urlopen',return_value=Response()),patch.dict(os.environ,{'ZZ_COLLECTOR_URL':'https://collector.invalid','ZZ_COLLECTOR_KEY':'test-only'}),patch('sys.argv',['run.py','--news-only','--collect','--publish']):run.main()
    build.assert_not_called();self.assertEqual(state['episodes'],original['episodes']);self.assertEqual(state['newsSeen'],original['newsSeen']);self.assertEqual(json.loads(Path(d,'collection-status.json').read_bytes())['coverage'],'partial');self.assertTrue(Path(d,'news-incidents.json').exists())

if __name__=='__main__':unittest.main()
