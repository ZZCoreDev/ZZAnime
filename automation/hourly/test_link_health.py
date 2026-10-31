"""Stored options whose provider page says the file was deleted leave the signed channel; anything doubtful stays."""
import datetime,gzip,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import link_health,run,voe_channel

FIX=json.loads(Path(__file__).with_name('link-fixtures.json').read_text(encoding='utf-8'))
ROOT='https://jkanime.net/tetsuryou-meet-with-tetsudou-musume/4/'
VOE='https://jkanime.net/chuubyou-gekihatsu-boy/9/'
DEAD_MP4='https://www.mp4upload.com/embed-nfxqz8214v7f.html'
LIVE_SW='https://hgcloud.to/e/hqp9yd62lqn4'
DEAD_VOE='https://voe.sx/e/yty6c7ob6jyw'
def iso(delta):return (datetime.datetime.now(datetime.timezone.utc)-delta).isoformat().replace('+00:00','Z')
def key(name,url):return run.sha((name+'\0'+url).encode())
def page(family,expect):return next((f['status'],f['body']) for f in FIX if f['family']==family and f['expect']==expect)
def shard(folder,url,providers):
 parent=url.rsplit('/',2)[0]+'/';path=Path(folder)/'series-state'/(hashlib.sha256(parent.encode()).hexdigest()+'.json.gz');path.parent.mkdir(parents=True,exist_ok=True)
 path.write_bytes(gzip.compress(json.dumps({'schema':1,'series':parent,'listing':{'complete':True,'observedAt':iso(datetime.timedelta(hours=2)),'episodes':[url]},'episodes':{url:{'complete':True,'observedAt':iso(datetime.timedelta(hours=2)),'providers':providers}}}).encode()))
def world(folder):
 shard(folder,ROOT,[{'family':'mp4upload','name':'Mp4upload','links':[DEAD_MP4]},{'family':'streamwish','name':'Streamwish','links':[LIVE_SW]}])
 shard(Path(folder)/'voe-state',VOE,[{'family':'voe','name':'voe','links':[DEAD_VOE]}])
 for side in (Path(folder),Path(folder)/'voe-state'):(side/'observations.json').write_text(json.dumps({'schema':1,'episodes':{},'listings':{},'pending':[],'newsSeen':{ROOT:iso(datetime.timedelta(hours=1)),VOE:iso(datetime.timedelta(hours=1))}}),encoding='utf-8')
class Web:
 """Real captured pages by URL; the fake id reads deleted exactly like a real deleted file."""
 def __init__(self,blocked=False):self.urls=[];self.blocked=blocked
 def __call__(self,url):
  self.urls.append(url)
  if self.blocked:return page('voe','dead')
  for family,host in [('mp4upload','mp4upload.com'),('streamwish','vibuxer.com'),('vidhide','callistanise.com'),('voe','voe.sx')]:
   if host in url:return page(family,'dead' if link_health.FAKE in url or url in (DEAD_MP4,DEAD_VOE) else 'alive')
  return 500,''
class LinkHealthTests(unittest.TestCase):
 def test_real_pages_classify_by_positive_markers_only(self):
  for f in FIX:self.assertEqual(link_health.classify(f['family'],f['status'],f['body']),f['expect'],f['url'])
  self.assertEqual(link_health.classify('mp4upload',503,'File was deleted'),'unknown')
  self.assertEqual(link_health.classify('voe',403,''),'unknown')
 def test_targets_stay_on_fixed_hosts(self):
  rules=link_health.policy()
  self.assertEqual(link_health.target('streamwish',LIVE_SW,rules),'https://'+rules['mirrors']['streamwish']+'/e/hqp9yd62lqn4')
  self.assertEqual(link_health.target('mp4upload','https://mp4upload.com/embed-nfxqz8214v7f.html',rules),DEAD_MP4)
  self.assertIsNone(link_health.target('voe','https://evil.example/e/abcdefgh1234',rules))
  self.assertIsNone(link_health.target('mega','https://mega.nz/file/x',rules))
 def test_mega_reads_the_public_api_by_file_id_only(self):
  rules=link_health.policy();key43='K'*43
  for link in ['https://mega.nz/file/AbCd1234#'+key43,'https://mega.nz/embed/AbCd1234#'+key43,'https://mega.nz/#!AbCd1234!'+key43,'https://mega.nz/embed#!AbCd1234!'+key43]:
   self.assertEqual(link_health.target('mega',link,rules),link_health.MEGA_API+'?id=0&file=AbCd1234',link)
  self.assertEqual(link_health.classify('mega',200,'[-9]'),'dead');self.assertEqual(link_health.classify('mega',200,'[-16]'),'dead')
  self.assertEqual(link_health.classify('mega',200,'[{"s":123,"at":"x","msd":1}]'),'alive')
  self.assertEqual(link_health.classify('mega',200,'[-3]'),'unknown');self.assertEqual(link_health.classify('mega',500,'[-9]'),'unknown')
 def test_device_reports_go_first_and_still_need_the_usual_evidence(self):
  # An old chapter outside the 7-day news list, reported by two devices through the help Worker.
  reported='https://www.mp4upload.com/embed-abcdefgh1234.html'
  with tempfile.TemporaryDirectory() as d:
   world(d);Path(d,'dead-reports.json').write_text(json.dumps({'links':[{'episode':'https://jkanime.net/old-show/3/','name':'Mp4upload','family':'mp4upload','url':reported,'devices':2}]}))
   web=Web();now=datetime.datetime.now(datetime.timezone.utc).timestamp()
   first=link_health.check(d,now=now,limit=1,fetcher=web,sleep=lambda s:None)
   # Its own slot plus the one regular slot; nothing is excluded on a single reading.
   self.assertIn(reported,web.urls);self.assertEqual((first['checked'],first['excluded']),(2,0))
   entry=json.loads(Path(d,'link-health.json').read_text())['links'][key('Mp4upload',reported)]
   self.assertEqual((entry['state'],entry.get('excluded')),('alive',False))
   # Still reported one hour later: checked again before the 24 h interval of a live link.
   web.urls.clear();link_health.check(d,now=now+3700,limit=1,fetcher=web,sleep=lambda s:None);self.assertIn(reported,web.urls)
 def test_reported_links_have_their_own_slots(self):
  reported=['https://www.mp4upload.com/embed-abcdefgh%04d.html'%i for i in range(12)]
  with tempfile.TemporaryDirectory() as d:
   world(d);Path(d,'dead-reports.json').write_text(json.dumps({'links':[{'episode':'https://jkanime.net/old-show/%d/'%(i+1),'name':'Mp4upload','family':'mp4upload','url':u,'devices':2} for i,u in enumerate(reported)]}))
   web=Web();now=datetime.datetime.now(datetime.timezone.utc).timestamp()
   s=link_health.check(d,now=now,limit=1,fetcher=web,sleep=lambda s:None)
   self.assertEqual(sum(u in web.urls for u in reported),link_health.REPORTED_LIMIT);self.assertEqual(s['checked'],link_health.REPORTED_LIMIT+1)
 def test_mega_downloads_are_checked_and_confirmed_deletions_leave_the_index(self):
  mega='https://mega.nz/file/AbCd1234#'+'K'*43;now=datetime.datetime.now(datetime.timezone.utc)
  with tempfile.TemporaryDirectory() as d:
   world(d);p=Path(d)/'series-state'/(hashlib.sha256(ROOT.rsplit('/',2)[0].encode()+b'/').hexdigest()+'.json.gz');row=json.loads(gzip.decompress(p.read_bytes()))
   row['episodes'][ROOT]['downloads']=[{'name':'Mega','family':'mega','url':mega}];p.write_bytes(gzip.compress(json.dumps(row).encode()))
   found=link_health.candidates(d,now.timestamp(),link_health.policy());k=key('Mega',mega)
   self.assertEqual((found[k]['family'],found[k].get('download')),('mega',True))
   Path(d,'link-health.json').write_text(json.dumps({'schema':1,'links':{k:{'excluded':True,'episode':ROOT}},'controls':{},'canaries':{}}))
   self.assertEqual(link_health.excluded_keys(d),{k})
  link='https://www.mp4upload.com/embed-a.html';state={'episodes':{ROOT:{'episode':ROOT,'complete':True,'observedAt':now.isoformat(),'providers':[{'name':'Mp4upload','family':'mp4upload','links':[link]}],'downloads':[{'name':'Mega','family':'mega','url':mega}]}},'listings':{ROOT.rsplit('/',2)[0]+'/':{'complete':True,'observedAt':now.isoformat(),'episodes':[ROOT]}}}
  approved={key('Mp4upload',link):True}
  def downloads(dead):
   _,files=run.build(state,approved,now,dead=dead);return json.loads(gzip.decompress(next(b for n,b in files.items() if n.startswith('series/'))))['episodes'][0].get('downloads')
  self.assertEqual(downloads(set())[0]['url'],mega);self.assertIsNone(downloads({k}))
 def test_deletion_needs_two_checks_thirty_minutes_apart_then_leaves_both_channels(self):
  with tempfile.TemporaryDirectory() as d:
   world(d);web=Web();now=datetime.datetime.now(datetime.timezone.utc).timestamp()
   first=link_health.check(d,now=now,fetcher=web,sleep=lambda s:None)
   self.assertEqual((first['dead'],first['alive'],first['excluded']),(2,1,0))
   self.assertEqual(link_health.check(d,now=now+600,fetcher=web,sleep=lambda s:None)['checked'],0)
   second=link_health.check(d,now=now+1900,fetcher=web,sleep=lambda s:None)
   self.assertEqual(second['excluded'],2)
   self.assertTrue(all('mp4upload.com' in u or 'vibuxer.com' in u or 'voe.sx' in u for u in web.urls))
   approved={key('Mp4upload',DEAD_MP4):True,key('Streamwish',LIVE_SW):True,key('voe',DEAD_VOE):True}
   self.assertEqual(link_health.exclude(d,approved),2)
   self.assertEqual(approved,{key('Mp4upload',DEAD_MP4):False,key('Streamwish',LIVE_SW):True,key('voe',DEAD_VOE):False})
 def test_uniform_not_found_pages_never_empty_a_provider(self):
  with tempfile.TemporaryDirectory() as d:
   world(d);web=Web(blocked=True);now=datetime.datetime.now(datetime.timezone.utc).timestamp()
   for at in (0,1900,4000,90000):link_health.check(d,now=now+at,fetcher=web,sleep=lambda s:None)
   self.assertEqual(json.loads(Path(d,'link-health.json').read_text())['last']['excluded'],0)
 def test_revived_file_returns(self):
  with tempfile.TemporaryDirectory() as d:
   world(d);now=datetime.datetime.now(datetime.timezone.utc).timestamp()
   for at in (0,1900):link_health.check(d,now=now+at,fetcher=Web(),sleep=lambda s:None)
   class Revived(Web):
    def __call__(self,url):return page('mp4upload','alive') if url==DEAD_MP4 else super().__call__(url)
   link_health.check(d,now=now+1900+49*3600,fetcher=Revived(),sleep=lambda s:None)
   approved={key('Mp4upload',DEAD_MP4):True};link_health.exclude(d,approved);self.assertTrue(approved[key('Mp4upload',DEAD_MP4)])
 def published_approval(self,folder):
  seen={}
  def command(args,**kw):
   if args[0]=='javac':return ''
   return '\n'.join(json.dumps({'key':run.sha((q['name']+'\0'+q['url']).encode()),'approved':True}) for q in map(json.loads,kw['input'].splitlines()))
  def build(state,approved,now,allow_voe=False,**extra):seen['voe' if allow_voe else 'root']=dict(approved);raise StopIteration
  with patch.object(run,'D',Path(folder)),patch.object(run,'command',side_effect=command),patch.object(run,'build',side_effect=build),patch('sys.argv',['run.py']):
   with self.assertRaises(StopIteration):run.main()
   with self.assertRaises(StopIteration):voe_channel.render(folder,datetime.datetime.now(datetime.timezone.utc),None,folder)
  return seen
 def test_signed_channels_withdraw_confirmed_deletions(self):
  with tempfile.TemporaryDirectory() as d:
   world(d);now=datetime.datetime.now(datetime.timezone.utc).timestamp()
   for at in (0,1900):link_health.check(d,now=now+at,fetcher=Web(),sleep=lambda s:None)
   seen=self.published_approval(d)
   self.assertFalse(seen['root'][key('Mp4upload',DEAD_MP4)]);self.assertTrue(seen['root'][key('Streamwish',LIVE_SW)])
   self.assertFalse(seen['voe'][key('voe',DEAD_VOE)])
 def test_disabled_policy_limits_exclusions_to_the_two_samples(self):
  with tempfile.TemporaryDirectory() as d:
   other='https://jkanime.net/ao-ashi/24/';Path(d).mkdir(exist_ok=True)
   Path(d,'link-health.json').write_text(json.dumps({'links':{'a':{'excluded':True,'episode':other},'b':{'excluded':True,'episode':ROOT}}}),encoding='utf-8')
   approved={'a':True,'b':True}
   with patch.object(link_health,'policy',return_value={'enabled':False,'proof':[ROOT]}):link_health.exclude(d,approved)
   self.assertEqual(approved,{'a':True,'b':False})
if __name__=='__main__':unittest.main()
