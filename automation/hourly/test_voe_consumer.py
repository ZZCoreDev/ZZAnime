"""Signed synthetic fixtures; no provider requests and no claimed playback."""
import datetime,json,tempfile,unittest
from pathlib import Path
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
import run
from voe_channel import PROOF

class ConsumerTests(unittest.TestCase):
 def test_real_old_and_new_readers_and_isolated_failure(self):
  now=datetime.datetime.now(datetime.timezone.utc);key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);site=root/'site';public=root/'key.der';public.write_bytes(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))
   for modern in [False,True]:
    state={'episodes':{},'listings':{}};approved={}
    for url in PROOF:
     parent=url.rsplit('/',2)[0]+'/';name='Voe' if modern else 'Mp4upload';family='voe' if modern else 'mp4upload';link='https://voe.sx/e/synthetic123' if modern else 'https://www.mp4upload.com/embed-synthetic.html'
     state['episodes'][url]={'episode':url,'complete':True,'observedAt':now.isoformat(),'providers':[{'name':name,'family':family,'links':[link]}]};state['listings'][parent]={'complete':True,'title':'Synthetic fixture','observedAt':now.isoformat(),'episodes':[url]};approved[run.sha((name+'\0'+link).encode())]=True
    index,files=run.build(state,approved,now,allow_voe=modern);body=run.raw(index);h=run.sha(body);path='indexes/'+h+'.bin';files[path]=body
    payload=run.raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':now.isoformat(),'indexPath':path,'indexSha256':h,'indexBytes':len(body),'mode':'daily-new'})
    files['channel.json']=run.raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})
    folder=site/'voe' if modern else site
    for n,b in files.items():run.put(folder/n,b)
   old=run.compile_java(root/'old');new=run.compile_java(root/'new',modern=True)
   legacy=json.loads(run.command(['java','-cp',old,'tv.jkanime.web.CloudVerify',str(site),str(public),str(root/'old-cache')]))
   self.assertEqual(legacy['episodes'],2)
   merged=json.loads(run.command(['java','-cp',new,'tv.jkanime.web.VoeOverlayAudit',str(public),str(root/'merged-cache'),'file:'+str(site)]))
   self.assertTrue(merged['twoSeriesMerged']);self.assertTrue(merged['legacyOptionsRetained']);self.assertTrue(merged['badSignatureIsolated']);self.assertTrue(merged['offlineCacheRetained']);self.assertFalse(merged['physicalAndroidPlayback'])

if __name__=='__main__':unittest.main()
