"""extraOptions (YourUpload, MixDrop on new hosts): only next to regular options, ignored by installed readers."""
import datetime,gzip,json,subprocess,tempfile,unittest
from pathlib import Path
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
import extra_options,link_health,run

URL='https://jkanime.net/serie-a/3/';PARENT='https://jkanime.net/serie-a/';MP4='https://www.mp4upload.com/embed-abcdefgh.html'
YU='https://www.yourupload.com/embed/abc123';MX='https://mixdrop.ps/e/abcd1234'
def key(name,url):return run.sha((name+'\0'+url).encode())
def state(now,providers=True):
 extra=[{'name':'YourUpload','family':'yourupload','links':[YU]},{'name':'MixDrop','family':'mixdrop','links':[MX,'https://evil.example/e/abcd']}]
 return {'episodes':{URL:{'episode':URL,'complete':True,'observedAt':now.isoformat(),'providers':[{'name':'Mp4upload','family':'mp4upload','links':[MP4]}] if providers else [],'extraProviders':extra}},
  'listings':{PARENT:{'complete':True,'observedAt':now.isoformat(),'episodes':[URL]}}}
def episodes(files):return [e for n,b in files.items() if n.startswith('series/') for e in json.loads(gzip.decompress(b))['episodes']]

class ExtraOptionsTests(unittest.TestCase):
 def setUp(self):self.now=datetime.datetime.now(datetime.timezone.utc)
 def test_validation_matches_the_new_app_rules(self):
  self.assertTrue(extra_options.valid('YourUpload','yourupload',YU));self.assertTrue(extra_options.valid('MixDrop','mixdrop',MX))
  for bad in [('YourUpload','yourupload','https://evil.example/embed/abc123'),('MixDrop','mixdrop','https://mixdrop.ps/e/abcd1234?x=1'),('MixDrop','mixdrop','https://mixdroop.bz/e/abcd1234'),('Mp4upload','yourupload',YU),('MixDrop','mixdrop','http://mixdroop.bz/e/abcd1234')]:
   with self.subTest(bad=bad):self.assertFalse(extra_options.valid(*bad))
  out=subprocess.run(['node','-e',"const r=require('./lib/backup-rules.cjs');console.log(JSON.stringify([r.extra('YourUpload','%s').family,r.extra('MixDrop','%s').name,r.extra('MixDrop','https://mxdrop.click/e/abcd1234'),r.family('YourUpload')]))"%(YU,MX)],capture_output=True,text=True,check=True,cwd=Path(__file__).parent).stdout
  self.assertEqual(json.loads(out),['yourupload','MixDrop',None,''])
 def test_published_only_next_to_regular_options_and_never_when_dead(self):
  approved={key('Mp4upload',MP4):True}
  _,files=run.build(state(self.now),approved,self.now)
  self.assertEqual([o['url'] for o in episodes(files)[0]['extraOptions']],[YU,MX])
  _,files=run.build(state(self.now),approved,self.now,dead={key('YourUpload',YU)})
  self.assertEqual([o['url'] for o in episodes(files)[0]['extraOptions']],[MX])
  with self.assertRaises(ValueError):run.build(state(self.now,providers=False),approved,self.now)  # no regular option: nothing published
 def test_link_checker_reads_youpload_404_as_deleted_and_needs_a_player_for_alive(self):
  rules=link_health.policy()
  self.assertEqual(link_health.target('yourupload','https://yourupload.com/embed/abc123',rules),YU)
  self.assertEqual(link_health.classify('yourupload',404,''),'dead');self.assertEqual(link_health.classify('yourupload',200,'<html>jwplayer(</html>'),'alive');self.assertEqual(link_health.classify('yourupload',200,'<html></html>'),'unknown')
 def test_installed_readers_ignore_extra_options(self):
  approved={key('Mp4upload',MP4):True};key_=rsa.generate_private_key(public_exponent=65537,key_size=2048);results=[]
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);public=root/'key.der';public.write_bytes(key_.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo));cp=run.compile_java(root/'old')
   for with_extra in (False,True):
    st=state(self.now)
    if not with_extra:st['episodes'][URL].pop('extraProviders')
    index,files=run.build(st,approved,self.now);body=run.raw(index);digest=run.sha(body);path='indexes/'+digest+'.bin';files[path]=body
    payload=run.raw({'schema':1,'sequence':int(self.now.timestamp()*1000),'createdAt':self.now.isoformat().replace('+00:00','Z'),'indexSha256':digest,'indexPath':path,'indexBytes':len(body),'mode':'daily-new'})
    site=root/('site'+str(len(results)))
    for n,b in {**files,'channel.json':run.raw({'payload':payload.decode(),'signature':key_.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})}.items():run.put(site/n,b)
    results.append(json.loads(run.command(['java','-cp',cp,'tv.jkanime.web.CloudVerify',str(site),str(public),str(root/('cache'+str(len(results))))])))
  self.assertEqual(results[0],results[1])
 def test_parked_mixdroop_is_never_valid_and_is_pruned(self):
  bz='https://mixdroop.bz/e/7rv8q14ncq87w4'
  self.assertFalse(extra_options.valid('MixDrop','mixdrop',bz))
  out=subprocess.run(['node','-e',"console.log(JSON.stringify(require('./lib/backup-rules.cjs').extra('MixDrop','%s')))"%bz],capture_output=True,text=True,check=True,cwd=Path(__file__).parent).stdout.strip()
  self.assertEqual(out,'null')
  ep={'providers':[],'extraProviders':[{'name':'YourUpload','family':'yourupload','links':[YU]},{'name':'MixDrop','family':'mixdrop','links':[bz]}]}
  self.assertEqual(extra_options.prune(ep)['extraProviders'],[ep['extraProviders'][0]]);self.assertEqual(len(ep['extraProviders']),2)
  clean={'extraProviders':[ep['extraProviders'][0]]};self.assertIs(extra_options.prune(clean),clean)

if __name__=='__main__':unittest.main()
