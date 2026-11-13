"""9/11: the owner view keeps only dead links (fields the editor shows), split under the 2 MB asset limit."""
import json,tempfile,unittest
from pathlib import Path
import owner_files
class OwnerFiles(unittest.TestCase):
    def test_parts(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);links={f'k{i}':{'state':'dead' if i%2 else 'alive','url':'https://example.com/'+'x'*400+str(i),'episode':'https://jkanime.net/a/1/','family':'f','deadChecks':[1,2],'archive':'big'} for i in range(20000)}
            (d/'link-health.json').write_text(json.dumps({'schema':1,'links':links,'last':{'tracked':20000,'dead':10000}}));(d/'help-status.json').write_text('{"worker":{}}')
            out=owner_files.build(d);manifest=json.loads(out['owner/link-health.json'])
            self.assertEqual(manifest['last']['dead'],10000);self.assertGreater(manifest['parts'],1)
            merged={}
            for n in range(manifest['parts']):
                b=out[f'owner/link-health-{n}.json'];self.assertLess(len(b),2097152);merged.update(json.loads(b)['links'])
            self.assertEqual(len(merged),10000);self.assertTrue(all(v['state']=='dead' and 'archive' not in v and 'deadChecks' not in v for v in merged.values()))
            self.assertIn('owner/help-status.json',out)
    def test_absent(self):
        with tempfile.TemporaryDirectory() as d:self.assertEqual(list(owner_files.build(d)),['owner/semaforo.json'])
    def test_semaforo(self):
        # 14/11: per family, only links checked in the 48 h before the last check; the JK copy status; no URLs
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);now=1_800_000_000
            links={'a':{'family':'voe','state':'alive','checkedAt':now-10,'url':'https://x/1'},'b':{'family':'voe','state':'dead','checkedAt':now-3600,'url':'https://x/2'},
                   'c':{'family':'mega','state':'unknown','checkedAt':now-100},'old':{'family':'mega','state':'dead','checkedAt':now-50*3600}}
            (d/'link-health.json').write_text(json.dumps({'schema':1,'links':links,'last':{'checkedAt':now}}))
            (d/'pc-import-status.json').write_text(json.dumps({'checkedAt':'2026-11-13T12:51:40+00:00','state':'imported','imported':61,'series':5,'batchSha256':'x'}))
            raw=owner_files.build(d)['owner/semaforo.json'];x=json.loads(raw)
            self.assertEqual(x['servers'],{'voe':{'alive':1,'dead':1,'unknown':0},'mega':{'alive':0,'dead':0,'unknown':1}})
            self.assertEqual(x['jk'],{'checkedAt':'2026-11-13T12:51:40+00:00','state':'imported','imported':61,'series':5})
            self.assertNotIn(b'https://',raw)
    def test_cloud_runs_with_the_cloud_token_only(self):
        import tempfile
        data={'workflow_runs':[{'name':'Capítulos nuevos cada 5 minutos','status':'completed','conclusion':'success','updated_at':'2026-11-10T08:00:00Z','workflow_id':7,'html_url':'https://github.com/x','actor':{'login':'secret-ish'}}]}
        with tempfile.TemporaryDirectory() as d:
            out=owner_files.build(d,token='t',fetch=lambda url:data)
            runs=json.loads(out['owner/cloud-runs.json'])['workflow_runs'];self.assertEqual(runs[0]['name'],'Capítulos nuevos cada 5 minutos');self.assertNotIn('actor',runs[0])
            self.assertNotIn('owner/cloud-runs.json',owner_files.build(d,token=''))
            def boom(url):raise OSError('offline')
            self.assertNotIn('owner/cloud-runs.json',owner_files.build(d,token='t',fetch=boom))
if __name__=='__main__':unittest.main()
