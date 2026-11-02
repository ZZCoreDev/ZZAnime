"""One device may renew a chapter only by re-confirming links the archive already approved. No network, fixed clock."""
import datetime,unittest
import help_chain
NOW=datetime.datetime(2026,11,2,12,tzinfo=datetime.timezone.utc)
URL='https://jkanime.net/serie-renovar/3/'
A='https://www.mp4upload.com/embed-aaaa1111.html';B='https://www.mp4upload.com/embed-bbbb2222.html';NEW='https://mega.nz/file/Nuevo123#k'
def iso(t):return t.isoformat().replace('+00:00','Z')
def state():
 return {'episodes':{URL:{'episode':URL,'complete':True,'observedAt':iso(NOW-datetime.timedelta(days=6)),'providers':[{'name':'Mp4upload','family':'mp4upload','links':[A,B]}]}},
  'listings':{'https://jkanime.net/serie-renovar/':{'complete':True,'observedAt':iso(NOW-datetime.timedelta(days=6)),'episodes':[URL]}}}
def answer(at=NOW-datetime.timedelta(hours=1),urls=(A,NEW)):
 return {'schema':1,'episodes':[],'renewals':[{'url':URL,'observedAt':iso(at),'options':[{'name':'Mp4upload' if 'mp4' in u else 'Mega','family':'mp4upload' if 'mp4' in u else 'mega','url':u} for u in urls]}]}
class SingleRenewalTests(unittest.TestCase):
 def test_renews_only_approved_links_still_listed_and_never_adds_new_ones(self):
  incoming,seen,held=help_chain.accept(answer(),state(),{URL},NOW,frozenset({URL}))
  ep=incoming['episodes'][URL]
  self.assertEqual(ep['observedAt'],iso(NOW-datetime.timedelta(hours=1)));self.assertEqual(ep['providers'],[{'name':'Mp4upload','family':'mp4upload','links':[A]}])
  self.assertNotIn(NEW,str(ep));self.assertEqual(ep['helpEvidence']['source'],'help-chain-single-renewal');self.assertEqual(seen,{})
 def test_ignored_when_not_asked_to_renew_or_stale_or_nothing_matches(self):
  for data,renew,reason in ((answer(),frozenset(),None),(answer(at=NOW-datetime.timedelta(days=8)),frozenset({URL}),'Stale or future renewal'),
                            (answer(at=NOW+datetime.timedelta(minutes=5)),frozenset({URL}),'Stale or future renewal'),(answer(urls=(NEW,)),frozenset({URL}),'Renewal saw none of the approved links')):
   with self.subTest(reason=reason):
    incoming,_,held=help_chain.accept(data,state(),{URL},NOW,renew)
    self.assertNotIn(URL,incoming['episodes'])
    if reason:self.assertEqual(held.get(URL),reason)
 def test_newer_stored_observation_wins(self):
  st=state();st['episodes'][URL]['observedAt']=iso(NOW-datetime.timedelta(minutes=10))
  incoming,_,held=help_chain.accept(answer(),st,{URL},NOW,frozenset({URL}))
  self.assertNotIn(URL,incoming['episodes']);self.assertEqual(held.get(URL),'Stored observation is newer')
 def test_readings_are_counted(self):
  # Rows, chapters not asked to renew and chapters without a stored observation are counted, nothing else changes.
  data=answer();data['renewals'].append({'url':'https://jkanime.net/otra/1/','observedAt':data['renewals'][0]['observedAt'],'options':[]})
  incoming,_,_=help_chain.accept(data,state(),{URL},NOW,frozenset({URL}))
  self.assertEqual(incoming['singleRenewal'],{'rows':2,'notAskedOrDone':1,'noStored':0,'renewed':1})
if __name__=='__main__':unittest.main()
