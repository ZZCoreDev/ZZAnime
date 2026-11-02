"""Spanish synopses: no network, fixed clock, fake AniList and fake Workers AI."""
import datetime,json,tempfile,unittest
from pathlib import Path
import synopsis_es as s
NOW=datetime.datetime(2026,11,2,12,tzinfo=datetime.timezone.utc)
EN_TEXT='Akko dreams of becoming a witch like her idol, so she enrolls at the academy where <i>magic</i> is taught.<br><br>(Source: Crunchyroll)'
ES_TEXT='Akko sueña con ser una bruja como su ídolo, así que se inscribe en la academia donde se enseña la magia a las chicas.'
class SynopsisTests(unittest.TestCase):
 def setUp(self):
  self.dir=Path(tempfile.mkdtemp());self.state=self.dir/'state.json';self.map=json.loads((s.HERE/'anilist-map.json').read_text(encoding='utf-8'))['items']
 def fetch(self,ids):return {'data':{'Page':{'media':[{'id':i,'description':EN_TEXT} for i in ids]}}}
 def test_clean_removes_markup_and_credit(self):
  self.assertEqual(s.clean(EN_TEXT),'Akko dreams of becoming a witch like her idol, so she enrolls at the academy where magic is taught.')
 def test_validation(self):
  src=s.clean(EN_TEXT)
  self.assertEqual(s.valid(src,ES_TEXT),'')
  self.assertEqual(s.valid(src,'Aquí tienes la traducción: '+ES_TEXT),'preamble')
  self.assertEqual(s.valid(src,src),'not-spanish')
  self.assertEqual(s.valid(src,'Corto.'),'empty')
 def test_translates_two_and_resumes_without_asking_again(self):
  r=s.run(self.state,2,NOW,self.fetch,lambda t:ES_TEXT)
  self.assertEqual(r['translated'],2);st=json.loads(self.state.read_text(encoding='utf-8'));item=st['items'][self.map[0]['url']]
  self.assertEqual((item['provenance'],item['source'],item['anilistId']),('ai-translated','anilist',self.map[0]['anilistId']))
  calls=[];r=s.run(self.state,2,NOW,self.fetch,lambda t:calls.append(t) or ES_TEXT)
  st=json.loads(self.state.read_text(encoding='utf-8'));self.assertEqual((len(calls),st['total']),(2,4));self.assertIn(self.map[3]['url'],st['items'])
 def test_rejected_translation_is_recorded_and_retried_another_day(self):
  r=s.run(self.state,1,NOW,self.fetch,lambda t:'Here is the translation.')
  st=json.loads(self.state.read_text(encoding='utf-8'));self.assertEqual(r['failed'],1);self.assertEqual(st['failed'][self.map[0]['url']]['reason'],'rejected-empty')
  self.assertEqual(s.run(self.state,1,NOW,self.fetch,lambda t:ES_TEXT)['asked'],1)  # next one, not the same day
  self.assertEqual(s.run(self.state,300,NOW+datetime.timedelta(days=1),self.fetch,lambda t:ES_TEXT)['asked'],len(self.map)-1)
 def test_budget_stops_before_the_free_allowance(self):
  st={'budget':{'day':'2026-11-02','neurons':s.DAILY_BUDGET-0.01}};self.state.write_text(json.dumps(st))
  r=s.run(self.state,5,NOW,self.fetch,lambda t:ES_TEXT);self.assertTrue(r['stoppedByBudget']);self.assertEqual(r['translated'],0)
 def test_series_without_description_is_not_sent_to_ai(self):
  r=s.run(self.state,1,NOW,lambda ids:{'data':{'Page':{'media':[{'id':i,'description':''} for i in ids]}}},lambda t:self.fail('AI called'))
  self.assertEqual(r['noDescription'],1)
if __name__=='__main__':unittest.main()
