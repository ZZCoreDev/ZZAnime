"""Ranking and option scores from device play votes; synthetic data, no Worker requests."""
import datetime,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import help_chain,plays,run

A='https://jkanime.net/serie-a/';B='https://jkanime.net/serie-b/'
def key(name,url):return hashlib.sha256((name+'\0'+url).encode()).hexdigest()
STATS={'options':[{'key':key('Mega','https://mega.nz/file/x'),'family':'mega','ok':5,'fail':1},{'key':'not-a-hash','ok':9,'fail':0}],
 'families':{'mega':[5,1],'streamwish':[1,4]},'popular':[{'series':A,'devices':7},{'series':'https://jkanime.net/no-publicada/','devices':5},{'series':B,'devices':1}]}
def state(now):
 link='https://www.mp4upload.com/embed-a.html';st={'episodes':{},'listings':{}}
 for parent in (A,B):
  url=parent+'1/';st['listings'][parent]={'complete':True,'observedAt':now.isoformat(),'episodes':[url]}
  st['episodes'][url]={'episode':url,'complete':True,'observedAt':now.isoformat(),'providers':[{'name':'Mp4upload','family':'mp4upload','links':[link]}]}
 return st,{run.sha(('Mp4upload\0'+link).encode()):True}

class PlaysTests(unittest.TestCase):
 def test_ranking_lists_published_series_with_two_devices_or_more(self):
  r=plays.ranking(STATS,{A,B},{A:'Serie A'})
  self.assertEqual(r['items'],[{'series':A,'title':'Serie A','devices':7}]);self.assertEqual((r['days'],r['basis']),(7,'distinct-devices'))
 def test_scores_keep_valid_keys_by_prefix(self):
  s=plays.scores(STATS)
  self.assertEqual(s['options'],{key('Mega','https://mega.nz/file/x')[:16]:[5,1]});self.assertEqual(s['families'],{'mega':[5,1],'streamwish':[1,4]})
 def test_index_carries_ranking_and_scores_and_drops_scores_first_near_the_limit(self):
  now=datetime.datetime.now(datetime.timezone.utc);st,approved=state(now)
  index,_=run.build(st,approved,now,plays=STATS)
  self.assertEqual([i['series'] for i in index['ranking']['items']],[A]);self.assertIn('playScores',index)
  with patch.object(run,'APP_INDEX_BYTES',len(run.raw(index))-1):small,_=run.build(st,approved,now,plays=STATS)
  self.assertNotIn('playScores',small);self.assertEqual(len(small['series']),2);self.assertIn('ranking',small)
  self.assertNotIn('ranking',run.build(st,approved,now)[0])
 def test_cloud_saves_the_worker_play_stats(self):
  def worker(path):return {'/v1/stats':{'schema':1},'/v1/dead-reports':{'links':[]},'/v1/play-stats':{'schema':1,**STATS}}[path]
  with tempfile.TemporaryDirectory() as d:
   help_chain.observe(Path(d),'https://help.invalid','k',datetime.datetime.now(datetime.timezone.utc),worker)
   self.assertEqual(plays.load(Path(d))['popular'][0]['series'],A)

if __name__=='__main__':unittest.main()
