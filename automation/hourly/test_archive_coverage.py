import datetime,unittest
from archive_coverage import audit,missing_targets
class CoverageTests(unittest.TestCase):
 def fixture(self):
  now=datetime.datetime.now(datetime.timezone.utc);a='https://jkanime.net/a/';b='https://jkanime.net/b/';return now,a,b,[{'url':a,'title':'A'},{'url':b,'title':'B'}]
 def test_missing_observed_movie_is_identified_in_batch(self):
  now,a,b,c=self.fixture();baseline={'series':{a:{'episodes':[a+'1/']},b:{'episodes':[b+'1/']}},'retained':{a+'1/':'Unapproved redirect',b+'1/':'Unapproved redirect'}}
  report=audit(c,baseline,{'episodes':{},'listings':{}},{},now.timestamp());self.assertEqual(report['missingChapters'],2);self.assertEqual(len(report['groups']['retained-redirect']),2);self.assertFalse(report['playbackVerified']);self.assertEqual(report['sourceRequests'],0)
 def test_existing_record_removes_obsolete_retained_incident(self):
  now,a,b,c=self.fixture();baseline={'series':{a:{'episodes':[a+'1/']}},'retained':{a+'1/':'Unapproved redirect'}};state={'episodes':{a+'1/':{'observedAt':now.isoformat(),'providers':[{'family':'mp4upload','links':['https://mp4upload.com/']}]}},'listings':{}}
  report=audit(c,baseline,state,{},now.timestamp());self.assertEqual(report['missingChapters'],0);self.assertNotIn('retained-redirect',report['groups']);self.assertEqual(report['seriesWithoutObservedListing'],1)
 def test_expiry_separate_from_presence_and_renewal_error(self):
  now,a,b,c=self.fixture();state={'episodes':{a+'1/':{'observedAt':(now-datetime.timedelta(days=8)).isoformat(),'providers':[]}},'listings':{a:{'episodes':[a+'1/']}}};report=audit(c,{},state,{a+'1/':{}},now.timestamp());self.assertEqual(report['storedChapters'],1);self.assertEqual(report['expiredChapters'],1);self.assertEqual(report['noIndependentChapters'],1);self.assertIn('renewal-error',report['groups'])
 def test_unknown_listing_does_not_invent_episode_one(self):
  now,a,b,c=self.fixture();report=audit(c,{}, {'episodes':{},'listings':{}},{},now.timestamp());self.assertEqual(report['observedChapters'],0);self.assertEqual(report['missingChapters'],0);self.assertEqual(report['seriesWithoutObservedListing'],2)
 def test_does_not_modify_originals(self):
  import copy
  now,a,b,c=self.fixture();baseline={'series':{a:{'episodes':[a+'1/']}}};before=copy.deepcopy(baseline);audit(c,baseline,{'episodes':{},'listings':{}},{},now.timestamp());self.assertEqual(baseline,before)
 def test_missing_targets_use_observed_records_and_skip_saved_or_paused(self):
  from unittest.mock import patch
  now,a,b,c=self.fixture();known={'series':{a:{'episodes':[a+'1/',a+'2/']},b:{'episodes':[b+'1/']}}};state={'episodes':{a+'1/':{}},'listings':{}}
  with patch('archive_coverage.baseline',return_value=known):
   self.assertEqual(missing_targets(state,{b+'1/':{'retryAt':now.timestamp()+100}},now.timestamp()),[a+'2/'])
 def test_unknown_series_never_generates_fake_first_episode(self):
  from unittest.mock import patch
  now,a,b,c=self.fixture()
  with patch('archive_coverage.baseline',return_value={'series':{}}):self.assertEqual(missing_targets({'episodes':{},'listings':{}},{},now.timestamp()),[])
 def test_failed_missing_chapter_is_reported_not_hidden_until_saved(self):
  now,a,b,c=self.fixture();report=audit(c,{'series':{a:{'episodes':[a+'1/']}}},{'episodes':{},'listings':{}},{a+'1/':{'reason':'Source HTTP 404'}},now.timestamp())
  self.assertEqual(report['series'][0]['renewalFailed'],1);self.assertEqual(report['groups']['renewal-error'][0]['samples'],[a+'1/']);self.assertEqual(report['missingChapters'],1)
 def test_chapters_published_in_voe_or_extra_are_counted_apart_not_missing(self):
  import tempfile
  from pathlib import Path
  from archive_state import save
  from archive_coverage import side_channels
  now,a,b,c=self.fixture();ep={'observedAt':now.isoformat(),'providers':[]}
  with tempfile.TemporaryDirectory() as temp:
   save(Path(temp)/'voe-state',{'episodes':{a+'1/':ep,a+'2/':ep},'listings':{a:{'episodes':[a+'1/',a+'2/']}}})
   save(Path(temp)/'extra-state',{'episodes':{a+'2/':ep,b+'1/':ep},'listings':{a:{'episodes':[a+'2/']},b:{'episodes':[b+'1/']}}})
   side=side_channels(temp)
  self.assertEqual(side,{a+'1/':{'voe'},a+'2/':{'voe','extra'},b+'1/':{'extra'}})
  baseline={'series':{a:{'episodes':[a+'1/',a+'2/',a+'3/']},b:{'episodes':[b+'1/',b+'2/']}}}
  report=audit(c,baseline,{'episodes':{},'listings':{}},{},now.timestamp(),side)
  self.assertEqual(report['missingChapters'],2);self.assertEqual(report['sideOnlyChapters'],3);self.assertEqual(report['voeOnlyChapters'],2);self.assertEqual(report['extraOnlyChapters'],2)
  self.assertEqual([row['missing'] for row in report['series']],[[a+'3/'],[b+'2/']]);self.assertEqual([row['sideOnly'] for row in report['series']],[2,1])
  self.assertEqual(audit(c,baseline,{'episodes':{},'listings':{}},{},now.timestamp())['missingChapters'],5)
if __name__=='__main__':unittest.main()
