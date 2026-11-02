"""Signed synthetic fixture; no provider requests. Chapters never expire (Robin 30/10): the cloud checker must accept
a published chapter older than seven days, as the installed app does, or every renewal stops at the final check."""
import datetime,json,tempfile,unittest
from pathlib import Path
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
import run
from voe_channel import PROOF

class OldChapterTests(unittest.TestCase):
 def test_cloud_checker_accepts_chapters_older_than_seven_days(self):
  now=datetime.datetime.now(datetime.timezone.utc);old=(now-datetime.timedelta(days=8)).isoformat();key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);site=root/'site';public=root/'key.der';public.write_bytes(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))
   state={'episodes':{},'listings':{}};approved={};name='Mp4upload';link='https://www.mp4upload.com/embed-synthetic.html'
   for url in PROOF:
    parent=url.rsplit('/',2)[0]+'/'
    state['episodes'][url]={'episode':url,'complete':True,'observedAt':old,'providers':[{'name':name,'family':'mp4upload','links':[link]}]};state['listings'][parent]={'complete':True,'title':'Synthetic fixture','observedAt':old,'episodes':[url]};approved[run.sha((name+'\0'+link).encode())]=True
   index,files=run.build(state,approved,now);body=run.raw(index);h=run.sha(body);path='indexes/'+h+'.bin';files[path]=body
   self.assertEqual(sum(x['episodes'] for x in index['series'].values()),2)
   payload=run.raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':now.isoformat(),'indexPath':path,'indexSha256':h,'indexBytes':len(body),'mode':'daily-new'})
   files['channel.json']=run.raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})
   for n,b in files.items():run.put(site/n,b)
   for modern in [False,True]:
    cp=run.compile_java(root/('new' if modern else 'old'),modern=modern)
    result=json.loads(run.command(['java','-cp',cp,'tv.jkanime.web.CloudVerify',str(site),str(public),str(root/('cache-'+str(modern)))]))
    self.assertEqual(result['episodes'],2)

if __name__=='__main__':unittest.main()
