"""16/11/2026: /latino/ complement (animeav1 dubbed es-LA links from the PC): strict import, app validator, signed channel."""
import datetime,gzip,json,tempfile,unittest
from pathlib import Path
import latino_channel as lc
from archive_state import load
NOW=datetime.datetime(2026,11,16,10,0,tzinfo=datetime.timezone.utc)
WHEN='2026-11-16T09:00:00+00:00'
KNOWN={'https://jkanime.net/sousou-no-frieren/':{'url':'https://jkanime.net/sousou-no-frieren/','title':'Sousou no Frieren'}}
def batch(**extra):
    ep={'checkedAt':WHEN,'options':[{'name':'VOE','url':'https://voe.sx/e/awqohxxe9wjk','lang':'es-LA'},{'name':'Filemoon','url':'https://bysekoze.com/e/70uodmr4hg98','lang':'es-LA'},
        {'name':'Mp4upload','url':'https://www.mp4upload.com/embed-csm6p9a7j1gh.html','lang':'es-LA'},{'name':'VOE','url':'https://evil.example/e/x','lang':'es-LA'},
        {'name':'VOE','url':'https://voe.sx/e/subtitulado','lang':'sub'},{'name':'Malo','url':'https://voe.sx/e/abcdefgh','lang':'es-LA'}]}
    return {'schema':1,'series':{'https://jkanime.net/sousou-no-frieren/':{'title':'Sousou no Frieren','episodes':{'https://jkanime.net/sousou-no-frieren/28/':ep,**extra}}}}
class Latino(unittest.TestCase):
    def test_candidates_strict(self):
        eps,listings,held=lc.candidates(batch(),NOW,KNOWN)
        ep=eps['https://jkanime.net/sousou-no-frieren/28/']
        self.assertEqual([(p['name'],p['links']) for p in ep['providers']],[('VOE',['https://voe.sx/e/awqohxxe9wjk']),('Filemoon',['https://bysekoze.com/e/70uodmr4hg98']),('Mp4upload',['https://www.mp4upload.com/embed-csm6p9a7j1gh.html'])])
        self.assertEqual(listings['https://jkanime.net/sousou-no-frieren/']['episodes'],['https://jkanime.net/sousou-no-frieren/28/'])
        bad=batch(**{'https://jkanime.net/otra-serie/1/':{'checkedAt':WHEN,'options':[]},'https://jkanime.net/sousou-no-frieren/0/':{'checkedAt':WHEN,'options':[]}})
        _,_,held=lc.candidates(bad,NOW,KNOWN);self.assertIn('https://jkanime.net/otra-serie/1/',held);self.assertIn('https://jkanime.net/sousou-no-frieren/0/',held)
        old=batch();old['series']['https://jkanime.net/sousou-no-frieren/']['episodes']['https://jkanime.net/sousou-no-frieren/28/']['checkedAt']='2026-11-01T00:00:00+00:00'
        eps,_,held=lc.candidates(old,NOW,KNOWN);self.assertFalse(eps);self.assertIn('Stale',list(held.values())[0])
        self.assertRaises(ValueError,lc.candidates,{'schema':2},NOW,KNOWN)
        _,_,held=lc.candidates({'schema':1,'series':{'https://jkanime.net/no-existe/':{'episodes':{}}}},NOW,KNOWN);self.assertIn('https://jkanime.net/no-existe/',held)
    def test_approve_and_signed_channel(self):
        eps,listings,_=lc.candidates(batch(),NOW,KNOWN)
        ok,held=lc.approve(eps,lambda q:{k:v['name']!='Filemoon' for k,v in q.items()})
        self.assertEqual([p['name'] for p in ok['https://jkanime.net/sousou-no-frieren/28/']['providers']],['VOE','Mp4upload'])
        none,held=lc.approve(eps,lambda q:{k:False for k in q});self.assertFalse(none);self.assertIn('approved',list(held.values())[0])
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'b.json.gz';f.write_bytes(gzip.compress(json.dumps(batch()).encode()))
            orig=lc.catalogue;lc.catalogue=lambda:KNOWN
            try:r=lc.import_batch(d,f,NOW,check=lambda q:{k:True for k in q})
            finally:lc.catalogue=orig
            self.assertEqual((r['imported'],r['series'],r['state']),(1,1,'imported'))
            r2=lc.import_batch(d,f,NOW,check=lambda q:{k:True for k in q}) if False else None
            state=load(Path(d)/lc.FOLDER);self.assertIn('https://jkanime.net/sousou-no-frieren/28/',state['episodes'])
            import run as p
            index,files=lc.build(state,NOW,p.sha,p.raw)
            body=json.loads(gzip.decompress(next(iter(files.values()))))
            self.assertEqual(body['lang'],'es-LA');opts=body['episodes'][0]['options']
            self.assertTrue(all(o['lang']=='es-LA' for o in opts));self.assertEqual({o['family'] for o in opts},{'voe','filemoon','mp4upload'})
            self.assertNotIn('evil',json.dumps(body))
if __name__=='__main__':unittest.main()
