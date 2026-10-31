"""Remote switches in the signed channel: strict validation, and installed readers ignore the field."""
import datetime,json,tempfile,unittest
from pathlib import Path
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
import remote_config as rc
import run

NOW=datetime.datetime(2026,10,31,1,0,tzinfo=datetime.timezone.utc)
def load(x):
 with tempfile.TemporaryDirectory() as d:
  p=Path(d,'c.json');p.write_text(json.dumps(x));return rc.load(NOW,p)
BASE={'schema':1,'version':3}

class RemoteConfigTests(unittest.TestCase):
 def test_shipped_file_matches_the_published_apps(self):
  c=rc.load(NOW)
  self.assertEqual(c['deviceHelp'],{'enabled':True,'tvShare':0.35,'mobileShare':0.12,'tvPages':24,'mobilePages':8,'renewFraction':0.67})
  self.assertEqual(c['deadReports'],{'enabled':True,'perDay':20});self.assertNotIn('notice',c);self.assertNotIn('minVersion',c)
 def test_missing_file_publishes_no_config(self):
  self.assertIsNone(rc.load(NOW,Path('/nonexistent/remote-config.json')))
 def test_rejects_anything_outside_the_known_knobs(self):
  for bad in [{**BASE,'workerUrl':'https://evil.example'},{**BASE,'version':0},{**BASE,'version':True},{'schema':2,'version':1},
              {**BASE,'deviceHelp':{'tvShare':1.5}},{**BASE,'deviceHelp':{'tvPages':2.5}},{**BASE,'deviceHelp':{'enabled':'yes'}},{**BASE,'deviceHelp':{'key':'x'}},
              {**BASE,'deadReports':{'perDay':-1}},{**BASE,'notice':{'id':'a b','text':'x'}},{**BASE,'notice':{'id':'a','text':''}},
              {**BASE,'notice':{'id':'a','text':'x','platforms':['web']}},{**BASE,'notice':{'id':'a','text':'x','until':'2026-11-02'}},
              {**BASE,'minVersion':{'tv':0}},{**BASE,'minVersion':{'ios':3}}]:
   with self.subTest(bad=bad),self.assertRaises(ValueError):load(bad)
 def test_notice_expires_and_values_are_normalised(self):
  c=load({**BASE,'notice':{'id':'nov2','text':'Actualiza antes del 2/11','until':'2026-11-02T23:00:00Z','platforms':['tv','tv']},'minVersion':{'tv':103,'mobile':78}})
  self.assertEqual(c['notice'],{'id':'nov2','text':'Actualiza antes del 2/11','until':'2026-11-02T23:00:00Z','platforms':['tv']})
  self.assertEqual(list(c['minVersion']),['mobile','tv'])
  self.assertNotIn('notice',load({**BASE,'notice':{'id':'old','text':'x','until':'2026-10-30T00:00:00Z'}}))
 def test_installed_readers_accept_channel_with_config_and_wanted(self):
  now=datetime.datetime.now(datetime.timezone.utc);url='https://jkanime.net/serie-a/3/';parent='https://jkanime.net/serie-a/';link='https://www.mp4upload.com/embed-a.html'
  state={'episodes':{url:{'episode':url,'complete':True,'observedAt':now.isoformat(),'providers':[{'name':'Mp4upload','family':'mp4upload','links':[link]}]}},'listings':{parent:{'complete':True,'observedAt':now.isoformat(),'episodes':[url]}}}
  approved={run.sha(('Mp4upload\0'+link).encode()):True};key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);public=root/'key.der';public.write_bytes(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))
   index,files=run.build(state,approved,now);body=run.raw(index);digest=run.sha(body);path='indexes/'+digest+'.bin';files[path]=body;cp=run.compile_java(root/'old');results=[]
   for extra in [{},{'wanted':[{'url':'https://jkanime.net/b/1/','number':1,'title':'B','renew':True}],'config':rc.load(now)}]:
    payload=run.raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':now.isoformat().replace('+00:00','Z'),'indexSha256':digest,'indexPath':path,'indexBytes':len(body),'mode':'daily-new',**extra})
    site=root/('site'+str(len(results)))
    for n,b in {**files,'channel.json':run.raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})}.items():run.put(site/n,b)
    results.append(json.loads(run.command(['java','-cp',cp,'tv.jkanime.web.CloudVerify',str(site),str(public),str(root/('cache'+str(len(results))))])))
   self.assertEqual(results[0],results[1])

if __name__=='__main__':unittest.main()
