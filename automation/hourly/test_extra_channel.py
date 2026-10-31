"""/extra/ complement: extra-only chapters kept apart from the root state, published signed. No network."""
import copy,datetime,gzip,json,tempfile,unittest
from pathlib import Path
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from archive_state import load
import extra_channel,renew,run

ONLY='https://jkanime.net/serie-x/2/';BOTH='https://jkanime.net/serie-x/3/';VOE='https://jkanime.net/serie-x/4/'
YU='https://www.yourupload.com/embed/abc123';MP4='https://www.mp4upload.com/embed-abcdefgh.html'
def iso(t):return t.isoformat().replace('+00:00','Z')
def incoming(now):
 x=[{'name':'YourUpload','family':'yourupload','links':[YU]}];ep=lambda url,providers:{'episode':url,'complete':True,'observedAt':iso(now),'providers':providers,'extraProviders':copy.deepcopy(x)}
 return {'episodes':{ONLY:ep(ONLY,[]),BOTH:ep(BOTH,[{'name':'Mp4upload','family':'mp4upload','links':[MP4]}]),VOE:ep(VOE,[{'name':'Voe','family':'voe','links':['https://voe.sx/e/abcdefgh']}])},
  'listings':{'https://jkanime.net/serie-x/':{'complete':True,'observedAt':iso(now),'episodes':[ONLY,BOTH,VOE]}}}

class ExtraChannelTests(unittest.TestCase):
 def setUp(self):self.now=datetime.datetime.now(datetime.timezone.utc)
 def test_renewal_accepts_extra_only_chapters(self):
  inc=incoming(self.now);t=self.now.timestamp()
  self.assertIs(renew.validate(inc,[ONLY,BOTH,VOE],t-10,t+10),inc)
  bad=incoming(self.now);bad['episodes'][ONLY].pop('extraProviders')
  with self.assertRaises(ValueError):renew.validate(bad,[ONLY,BOTH,VOE],t-10,t+10)
 def test_split_keeps_root_untouched_and_moves_extra_only_chapters(self):
  with tempfile.TemporaryDirectory() as d:
   rest,count=extra_channel.split(d,incoming(self.now))
   self.assertEqual(count,2)  # extra-only and VOE+extra (no regular provider)
   self.assertNotIn(ONLY,rest['episodes']);self.assertIn(VOE,rest['episodes']);self.assertNotIn('extraProviders',rest['episodes'][VOE])
   self.assertIn('extraProviders',rest['episodes'][BOTH])  # regular chapter keeps its extras for root extraOptions
   side=load(Path(d)/extra_channel.FOLDER);self.assertEqual(set(side['episodes']),{ONLY,VOE});self.assertEqual(side['episodes'][ONLY]['providers'],[])
   self.assertEqual(extra_channel.split(d,incoming(self.now))[1],0)  # same observation twice: nothing new
 def test_signed_channel_with_empty_options_and_extra_options(self):
  key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  with tempfile.TemporaryDirectory() as d:
   extra_channel.split(d,incoming(self.now))
   files=extra_channel.render(d,self.now,key,set())
   wrapper=json.loads(files['extra/channel.json']);payload=wrapper['payload'].encode()
   key.public_key().verify(bytes.fromhex(wrapper['signature']),payload,padding.PKCS1v15(),hashes.SHA256())
   p=json.loads(payload);index=json.loads(files['extra/'+p['indexPath']])
   self.assertEqual(run.sha(files['extra/'+p['indexPath']]),p['indexSha256'])
   row=json.loads(gzip.decompress(files['extra/'+next(iter(index['series'].values()))['path']]))
   self.assertEqual([(e['url'],e['options'],[o['url'] for o in e['extraOptions']]) for e in row['episodes']],[(ONLY,[],[YU]),(VOE,[],[YU])])
   self.assertEqual(extra_channel.render(d,self.now,key,{run.sha(('YourUpload\0'+YU).encode())}),{})  # all dead: nothing to publish
 def test_render_removes_stored_mixdroop_links(self):
  import datetime,extra_channel,tempfile
  from pathlib import Path
  from archive_state import load,save
  from cryptography.hazmat.primitives.asymmetric import rsa
  now=datetime.datetime.now(datetime.timezone.utc);yu='https://www.yourupload.com/embed/abc123'
  a,b='https://jkanime.net/heine/1/','https://jkanime.net/solo/1/'
  st={'episodes':{a:{'complete':True,'observedAt':now.isoformat(),'providers':[],'extraProviders':[{'name':'YourUpload','family':'yourupload','links':[yu]},{'name':'MixDrop','family':'mixdrop','links':['https://mixdroop.bz/e/7rv8q14ncq87w4']}]},
   b:{'complete':True,'observedAt':now.isoformat(),'providers':[],'extraProviders':[{'name':'MixDrop','family':'mixdrop','links':['https://mixdroop.bz/e/abcd1234']}]}},
   'listings':{'https://jkanime.net/heine/':{'complete':True,'observedAt':now.isoformat(),'episodes':[a]},'https://jkanime.net/solo/':{'complete':True,'observedAt':now.isoformat(),'episodes':[b]}},'pending':[]}
  with tempfile.TemporaryDirectory() as d:
   save(Path(d)/'extra-state',st);files=extra_channel.render(d,now,rsa.generate_private_key(public_exponent=65537,key_size=2048),set())
   kept=load(Path(d)/'extra-state')['episodes']
   self.assertEqual(kept[a]['extraProviders'],[{'name':'YourUpload','family':'yourupload','links':[yu]}]);self.assertEqual(kept[b]['extraProviders'],[])
   self.assertFalse(any(b'mixdroop' in body for body in files.values()))
   self.assertEqual(sum(n.startswith('extra/series/') for n in files),1)

if __name__=='__main__':unittest.main()
