"""Intro/ending marks in the published index; synthetic data, no Worker requests."""
import datetime,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import help_chain,run,skip_marks

A='https://jkanime.net/serie-a/1/'
MARKS={'marks':[{'episode':A,'kind':'intro','start':91,'stop':181,'devices':3},{'episode':A,'kind':'outro','start':1300,'stop':1390,'devices':2},
 {'episode':'https://jkanime.net/no-publicada/1/','kind':'intro','start':10,'stop':100,'devices':5},{'episode':A,'kind':'recap','start':0,'stop':30,'devices':4},
 {'episode':A,'kind':'intro','start':100,'stop':900,'devices':9}]}
def state(now):
 link='https://www.mp4upload.com/embed-a.html'
 return ({'episodes':{A:{'episode':A,'complete':True,'observedAt':now.isoformat(),'providers':[{'name':'Mp4upload','family':'mp4upload','links':[link]}]}},
  'listings':{'https://jkanime.net/serie-a/':{'complete':True,'observedAt':now.isoformat(),'episodes':[A]}}},{run.sha(('Mp4upload\0'+link).encode()):True})

class SkipMarksTests(unittest.TestCase):
 def test_only_published_chapters_valid_kinds_and_lengths(self):
  self.assertEqual(skip_marks.build(MARKS,{A})['items'],{'serie-a/1':{'intro':[91,181],'outro':[1300,1390]}})
 def test_cap_keeps_the_most_agreed_first(self):
  many={'marks':[{'episode':'https://jkanime.net/s/%d/'%(i+1),'kind':'intro','start':1,'stop':60} for i in range(skip_marks.MAX_ITEMS+5)]}
  self.assertEqual(len(skip_marks.build(many,{m['episode'] for m in many['marks']})['items']),skip_marks.MAX_ITEMS)
 def test_index_carries_marks_and_drops_them_first_near_the_limit(self):
  now=datetime.datetime.now(datetime.timezone.utc);st,approved=state(now)
  index,_=run.build(st,approved,now,marks=MARKS);self.assertEqual(index['skipMarks']['items']['serie-a/1']['intro'],[91,181])
  with patch.object(run,'APP_INDEX_BYTES',len(run.raw(index))-1):small,_=run.build(st,approved,now,marks=MARKS)
  self.assertNotIn('skipMarks',small);self.assertEqual(len(small['series']),1)
 def test_cloud_saves_the_worker_marks(self):
  def worker(path):return {'/v1/stats':{},'/v1/dead-reports':{'links':[]},'/v1/play-stats':{},'/v1/marks-stats':{'schema':1,**MARKS}}[path]
  with tempfile.TemporaryDirectory() as d:
   help_chain.observe(Path(d),'https://help.invalid','k',datetime.datetime.now(datetime.timezone.utc),worker)
   self.assertEqual(len(skip_marks.load(Path(d))['marks']),5)

if __name__=='__main__':unittest.main()
