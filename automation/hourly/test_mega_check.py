"""MEGA from AnimeFLV/TioAnime only when the API reads it alive; «SW» published as «Streamwish». No network."""
import datetime,json,subprocess,tempfile,unittest
from pathlib import Path
import mega_check,run

K='K'*43
FLV='https://jkanime.net/serie-flv/3/';TIO='https://jkanime.net/serie-tio/4/';JK='https://jkanime.net/serie-jk/5/'
ALIVE='https://mega.nz/embed/Aliv1234#'+K;LOGIN='https://mega.nz/embed/Logn1234#'+K;GONE='https://mega.nz/file/Gone1234#'+K;MP4='https://www.mp4upload.com/embed-abcdefgh.html'
def key(name,url):return run.sha((name+'\0'+url).encode())
def state(now):
 ep=lambda url,**x:{'episode':url,'complete':True,'observedAt':now.isoformat(),**x}
 return {'episodes':{
  FLV:ep(FLV,sourceSeries='https://vww.animeflv.one/anime/serie-flv',providers=[{'name':'Mp4upload','family':'mp4upload','links':[MP4]}],reviewProviders=[{'name':'Mega','family':'mega','links':[ALIVE]}]),
  TIO:ep(TIO,sourceSeries='https://tioanime.com/anime/serie-tio',providers=[{'name':'Mega','family':'mega','links':[LOGIN,GONE]}]),
  JK:ep(JK,providers=[{'name':'Mega','family':'mega','links':['https://mega.nz/embed/Jkkk1234#'+K]}])},
  'listings':{u.rsplit('/',2)[0]+'/':{'complete':True,'observedAt':now.isoformat(),'episodes':[u]} for u in (FLV,TIO,JK)}}
def api(url):
 file=url.rsplit('=',1)[1]
 return {'Aliv1234':(200,'[{"s":1234,"at":"x","msd":1}]'),'Logn1234':(200,'[-6]'),'Gone1234':(200,'[-9]')}[file]

class MegaCheckTests(unittest.TestCase):
 def setUp(self):self.now=datetime.datetime.now(datetime.timezone.utc);self.st=state(self.now)
 def test_candidates_are_flv_review_and_tio_mega_only(self):
  self.assertEqual(set(mega_check.candidates(self.st)),{key('Mega',ALIVE),key('Mega',LOGIN),key('Mega',GONE)})
 def test_only_alive_answers_count_with_limit_pause_and_cache(self):
  pauses=[];t=self.now.timestamp()
  with tempfile.TemporaryDirectory() as d:
   s=mega_check.check(d,self.st,now=t,limit=2,fetcher=api,sleep=pauses.append)
   self.assertEqual((s['checked'],len(pauses)),(2,1))
   s=mega_check.check(d,self.st,now=t+60,limit=5,fetcher=api,sleep=pauses.append)
   self.assertEqual(s['checked'],1)  # only the one not asked yet
   self.assertEqual(mega_check.alive(d,t+60),{key('Mega',ALIVE)})
   self.assertEqual(mega_check.check(d,self.st,now=t+120,fetcher=api,sleep=pauses.append)['checked'],0)
   self.assertEqual(mega_check.check(d,self.st,now=t+60+mega_check.RETRY_AFTER+1,fetcher=api,sleep=pauses.append)['checked'],2)  # both rejected asked again
   self.assertEqual(mega_check.alive(d,t+mega_check.ALIVE_FOR+1),set())
 def test_errors_never_count_as_alive(self):
  def broken(url):raise OSError('down')
  with tempfile.TemporaryDirectory() as d:
   mega_check.check(d,self.st,now=self.now.timestamp(),fetcher=broken,sleep=lambda s:None);self.assertEqual(mega_check.alive(d,self.now.timestamp()),set())
 def test_build_publishes_flv_review_and_tio_mega_only_when_alive(self):
  approved={key('Mp4upload',MP4):True,key('Mega',ALIVE):True,key('Mega',LOGIN):True,key('Mega',GONE):True,key('Mega','https://mega.nz/embed/Jkkk1234#'+K):True}
  def urls(alive):
   _,files=run.build(self.st,approved,self.now,mega_alive=alive)
   return sorted(o['url'] for n,b in files.items() if n.startswith('series/') for e in json.loads(__import__('gzip').decompress(b))['episodes'] for o in e['options'])
  self.assertNotIn(ALIVE,urls(set()));self.assertNotIn(LOGIN,urls(set()))
  self.assertIn(ALIVE,urls({key('Mega',ALIVE)}));self.assertNotIn(LOGIN,urls({key('Mega',ALIVE)}))
  self.assertIn('https://mega.nz/embed/Jkkk1234#'+K,urls(set()))  # JK's own MEGA is unchanged

class StreamwishNameTests(unittest.TestCase):
 def test_sw_label_becomes_streamwish_which_installed_apps_approve(self):
  out=subprocess.run(['node','-e',"const r=require('./lib/backup-rules.cjs');console.log(JSON.stringify([r.canonical('SW'),r.family('SW'),r.canonical('SW 2'),r.canonical('Swish')]))"],capture_output=True,text=True,check=True,cwd=Path(__file__).parent).stdout
  self.assertEqual(json.loads(out),['Streamwish','streamwish','Streamwish','Swish'])
  with tempfile.TemporaryDirectory() as d:
   cp=run.compile_java(Path(d)/'c');link='https://streamwish.to/e/abcdefgh1234'
   res=[json.loads(l)['approved'] for l in run.command(['java','-cp',cp,'tv.jkanime.web.RuntimeOptionAudit'],input='\n'.join(json.dumps({'name':n,'url':link}) for n in ('SW','Streamwish'))).splitlines()]
  self.assertEqual(res,[False,True])

if __name__=='__main__':unittest.main()
