import datetime,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import news_watchdog as w
class WatchdogTests(unittest.TestCase):
 def test_two_series_and_incremental_freshness(self):
  for series in ['psyren','dark-summoner-to-dekiteiru']:
   with self.subTest(series=series),tempfile.TemporaryDirectory() as d:
    p=Path(d);original={'series':series,'episodes':[1,2,3,4]};(p/'original.json').write_text(json.dumps(original))
    self.assertTrue(w.due(p,1000))
    def collect(*args,**kw):
     self.assertEqual(args[0][-2:],['--collect','--publish']);self.assertTrue(kw['check']);(p/'collection-status.json').write_text(json.dumps({'state':'complete','checkedAt':'1970-01-01T00:16:40Z'}))
    with patch.dict(os.environ,{'ZZ_NEWS_WATCHDOG_ENABLED':'true'}),patch.object(w.time,'time',return_value=1000),patch.object(w.subprocess,'run',side_effect=collect) as run:
     self.assertTrue(w.check(p));self.assertFalse(w.check(p));self.assertEqual(run.call_count,1)
    self.assertEqual(json.loads((p/'original.json').read_text()),original)
 def test_boundary_and_future_clock(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'collection-status.json').write_text(json.dumps({'state':'complete','checkedAt':'1970-01-01T00:16:40Z'}))
   self.assertFalse(w.due(p,1299));self.assertTrue(w.due(p,1300));self.assertTrue(w.due(p,999))
 def test_failure_retries_without_erasing(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'keep.bin').write_bytes(b'original');
   with patch.dict(os.environ,{'ZZ_NEWS_WATCHDOG_ENABLED':'true'}),patch.object(w.time,'time',return_value=1000),patch.object(w.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'collector')):
    self.assertTrue(w.check(p));self.assertFalse(w.check(p))
   row=json.loads((p/'news-watchdog.json').read_text());self.assertEqual(row['state'],'failed');self.assertEqual(row['retryAt'],1900);self.assertEqual((p/'keep.bin').read_bytes(),b'original')
 def test_disabled_has_no_effect(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'ZZ_NEWS_WATCHDOG_ENABLED':'false'}),patch.object(w.subprocess,'run') as run:
   self.assertFalse(w.check(d));run.assert_not_called();self.assertEqual(list(Path(d).iterdir()),[])
 def test_corrupt_status_never_fakes_freshness(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'collection-status.json').write_text('broken');self.assertTrue(w.due(p,1000))
if __name__=='__main__':unittest.main()
