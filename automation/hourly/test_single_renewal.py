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
 def test_single_reading_never_replaces_the_chapter(self):
  # 11/11 auditoría S-04: one device's reading must not cut options (A,B -> A) nor renew the date.
  incoming,seen,held=help_chain.accept(answer(),state(),{URL},NOW,frozenset({URL}))
  self.assertNotIn(URL,incoming['episodes']);self.assertEqual(seen,{})
if __name__=='__main__':unittest.main()
