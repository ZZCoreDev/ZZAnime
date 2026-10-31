"""Derived weekly schedule and the installed-app limits on the published index; synthetic data only."""
import datetime,unittest
from unittest.mock import patch
import run,schedule

def z(t):return t.isoformat().replace('+00:00','Z')
def state_for(now,series):
 # series: {slug: [(number, first seen, observed)]}
 st={'episodes':{},'listings':{},'newsSeen':{}};link='https://www.mp4upload.com/embed-a.html'
 for slug,eps in series.items():
  parent='https://jkanime.net/'+slug+'/';st['listings'][parent]={'complete':True,'observedAt':z(now),'episodes':[]}
  for n,seen,observed in eps:
   url=parent+str(n)+'/';st['listings'][parent]['episodes'].append(url)
   st['episodes'][url]={'episode':url,'complete':True,'observedAt':z(observed),'providers':[{'name':'Mp4upload','family':'mp4upload','links':[link]}]}
   if seen:st['newsSeen'][url]=z(seen)
 return st,{run.sha(('Mp4upload\0'+link).encode()):True}

class ScheduleTests(unittest.TestCase):
 def test_weekday_and_time_in_madrid_across_the_october_clock_change(self):
  now=datetime.datetime(2026,10,31,22,0,tzinfo=datetime.timezone.utc)
  st,_=state_for(now,{'a':[(5,datetime.datetime(2026,10,31,19,30,tzinfo=datetime.timezone.utc),now)],'b':[(9,datetime.datetime(2026,10,24,18,0,tzinfo=datetime.timezone.utc),now)]})
  items=schedule.build(st,set(st['episodes']),now,{'https://jkanime.net/a/':'Serie A'})['items']
  # 31/10 is CET (UTC+1); 24/10 was still CEST (UTC+2).
  self.assertEqual([(i['series'].split('/')[3],i['weekday'],i['time'],i['episode']) for i in items],[('b',6,'20:00',9),('a',6,'20:30',5)])
  self.assertEqual(items[1]['title'],'Serie A')
 def test_latest_chapter_only_available_and_in_window(self):
  now=datetime.datetime(2026,10,31,12,0,tzinfo=datetime.timezone.utc);d=lambda h:now-datetime.timedelta(hours=h)
  st,_=state_for(now,{'a':[(3,d(170),now),(4,d(2),now)],'gone':[(1,d(5),now)],'old':[(2,d(24*9),now)]})
  available=set(st['episodes'])-{'https://jkanime.net/gone/1/'}
  self.assertEqual([(i['series'].split('/')[3],i['episode']) for i in schedule.build(st,available,now,{})['items']],[('a',4)])
 def test_published_index_carries_the_schedule(self):
  now=datetime.datetime.now(datetime.timezone.utc)
  st,approved=state_for(now,{'a':[(1,now-datetime.timedelta(hours=1),now)]})
  index,_=run.build(st,approved,now);self.assertEqual(index['schedule']['items'][0]['url'],'https://jkanime.net/a/1/')

class AppLimitTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime.datetime.now(datetime.timezone.utc);h=lambda n:self.now-datetime.timedelta(hours=n)
  self.st,self.approved=state_for(self.now,{'newest':[(1,None,h(1))],'middle':[(1,None,h(50))],'oldest':[(1,None,h(900))]})
 def test_series_limit_drops_the_least_recently_observed_never_the_channel(self):
  with patch.object(run,'APP_SERIES_LIMIT',2):index,files=run.build(self.st,self.approved,self.now)
  kept={run.sha(('https://jkanime.net/'+s+'/').encode()) for s in ('newest','middle')}
  self.assertEqual(set(index['series']),kept);self.assertEqual(len([f for f in files if f.startswith('series/')]),2)
 def test_index_size_limit_drops_oldest_until_it_fits(self):
  full,_=run.build(self.st,self.approved,self.now);size=len(run.raw(full))
  with patch.object(run,'APP_INDEX_BYTES',size-1):index,files=run.build(self.st,self.approved,self.now)
  self.assertEqual(len(index['series']),2);self.assertNotIn(run.sha(b'https://jkanime.net/oldest/'),index['series'])
  self.assertEqual({e['path'] for e in index['series'].values()},{f for f in files if f.startswith('series/')})

if __name__=='__main__':unittest.main()
