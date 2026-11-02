"""Untrusted/legacy device summaries never reach the signed index. No network, fixed clock."""
import copy,datetime,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import help_chain,plays,run,skip_marks

NOW=datetime.datetime(2026,11,2,12,tzinfo=datetime.timezone.utc)
SERIES='https://jkanime.net/security-fixture/'
EPISODE=SERIES+'1/'
KEY=hashlib.sha256(b'Mp4upload\0https://www.mp4upload.com/embed-fixture.html').hexdigest()
def attested(**sections):
 return {'schema':1,'evidencePolicy':'network-v2','basis':'independent-networks','generatedAt':NOW.isoformat(),
  'minDeviceAgeHours':24,'complete':True,**sections}
def play_stats():
 return attested(options=[{'key':KEY,'family':'mp4upload','ok':3,'fail':0,'independentNetworks':3}],
  families={'mp4upload':[3,0]},popular=[{'series':SERIES,'devices':2,'independentNetworks':2}])
def mark_stats():
 return attested(marks=[{'episode':EPISODE,'kind':'intro','start':10,'stop':100,'devices':2,'independentNetworks':2}])
def fixture():
 stamp=NOW.isoformat();link='https://www.mp4upload.com/embed-fixture.html'
 return ({'episodes':{EPISODE:{'episode':EPISODE,'complete':True,'observedAt':stamp,'providers':[{'name':'Mp4upload','family':'mp4upload','links':[link]}]}},
  'listings':{SERIES:{'complete':True,'observedAt':stamp,'episodes':[EPISODE]}}},{KEY:True})

class SignalSecurityTests(unittest.TestCase):
 def test_direct_helpers_reject_unattested_lists(self):
  legacy_play={k:v for k,v in play_stats().items() if k in ('options','families','popular')}
  legacy_marks={'marks':mark_stats()['marks']}
  self.assertIsNone(plays.ranking(legacy_play,{SERIES},{}))
  self.assertIsNone(plays.scores(legacy_play))
  self.assertIsNone(skip_marks.build(legacy_marks,{EPISODE}))

 def test_build_never_signs_legacy_or_unknown_policy_even_when_passed_directly(self):
  state,approved=fixture()
  for change in ({'evidencePolicy':'old'},{'complete':False},{'minDeviceAgeHours':0},{'basis':'distinct-devices'}):
   with self.subTest(change=change):
    p,m=play_stats(),mark_stats();p.update(change);m.update(change)
    index,_=run.build(state,approved,NOW,plays=p,marks=m)
    self.assertNotIn('ranking',index);self.assertNotIn('playScores',index);self.assertNotIn('skipMarks',index)
    self.assertEqual(index['series'][run.sha(SERIES.encode())]['episodes'],1)

 def test_future_stale_missing_or_bad_timestamps_are_ignored(self):
  state,approved=fixture()
  for stamp in ((NOW+datetime.timedelta(minutes=5,seconds=1)).isoformat(),(NOW-datetime.timedelta(days=1,seconds=1)).isoformat(),'garbage','2026-11-02'):
   with self.subTest(stamp=stamp):
    p,m=play_stats(),mark_stats();p['generatedAt']=m['generatedAt']=stamp
    index,_=run.build(state,approved,NOW,plays=p,marks=m)
    self.assertTrue({'ranking','playScores','skipMarks'}.isdisjoint(index))
  p=play_stats();del p['generatedAt']
  self.assertNotIn('playScores',run.build(state,approved,NOW,plays=p)[0])

 def test_invalid_counts_do_not_become_scores_ranking_or_marks(self):
  state,approved=fixture()
  for bad in (True,'3',-1,1.5,2**80,None):
   with self.subTest(bad=bad):
    p,m=play_stats(),mark_stats();p['options'][0]['ok']=bad;p['families']['mp4upload']=[bad,0]
    p['popular'][0]['independentNetworks']=bad;m['marks'][0]['independentNetworks']=bad
    index,_=run.build(state,approved,NOW,plays=p,marks=m)
    self.assertTrue({'ranking','playScores','skipMarks'}.isdisjoint(index))
  p,m=play_stats(),mark_stats();p['options'][0]['independentNetworks']=2;p['families']={'mp4upload':[1,1]}
  p['popular'][0]['devices']=99;m['marks'][0]['devices']=99
  self.assertTrue({'ranking','playScores','skipMarks'}.isdisjoint(run.build(state,approved,NOW,plays=p,marks=m)[0]))

 def test_legacy_and_corrupt_cache_are_ignored_without_deleting_files(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)
   for content in ('{broken', '[]', 'null', json.dumps({'options':[],'popular':[],'marks':[]})):
    for filename,loader in (('play-stats.json',plays.load),('marks.json',skip_marks.load)):
     with self.subTest(filename=filename,content=content):
      path=folder/filename;path.write_text(content,encoding='utf-8')
      self.assertIsNone(loader(folder));self.assertEqual(path.read_text(encoding='utf-8'),content)

 def test_observer_preserves_attestation_and_fixed_clock_reaches_signed_index(self):
  p,m=play_stats(),mark_stats()
  def worker(path):return {'/v1/stats':{},'/v1/dead-reports':{'links':[]},'/v1/play-stats':p,'/v1/marks-stats':m}[path]
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);help_chain.observe(folder,'https://unused.invalid','test-only',NOW,worker)
   saved=json.loads((folder/'play-stats.json').read_bytes())
   self.assertEqual(saved['evidencePolicy'],'network-v2');self.assertTrue(saved['complete']);self.assertEqual(saved['generatedAt'],p['generatedAt'])
   state,approved=fixture()
   index,_=run.build(state,approved,NOW,plays=plays.load(folder,now=NOW),marks=skip_marks.load(folder,now=NOW))
   self.assertIn('ranking',index);self.assertIn('playScores',index);self.assertIn('skipMarks',index)

 def test_bad_or_unavailable_summaries_never_block_collection_or_rewrite_legacy(self):
  for bad in (None,[],{'options':[],'popular':[]},{'error':'offline'}):
   with self.subTest(bad=bad),tempfile.TemporaryDirectory() as d:
    folder=Path(d);old=b'{"legacy":true}';(folder/'play-stats.json').write_bytes(old)
    help_chain.observe(folder,'https://unused.invalid','test-only',NOW,lambda path:bad)
    self.assertEqual((folder/'play-stats.json').read_bytes(),old)
    state,approved=fixture();index,_=run.build(state,approved,NOW,plays=plays.load(folder))
    self.assertEqual(len(index['series']),1);self.assertTrue({'ranking','playScores','skipMarks'}.isdisjoint(index))

if __name__=='__main__':unittest.main()
