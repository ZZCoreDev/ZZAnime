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
    def test_dead_reports_checked(self):
        """17/11 (Robin): people's reports reach the owner's editor only with clean fields; bad ones are dropped."""
        ok={'episode':'https://jkanime.net/sousou-no-frieren/3/','name':'VOE','family':'VOE','url':'https://voe.sx/e/abcdefgh','devices':3,'asns':2,'first':1763300000000}
        bad=[dict(ok,url='javascript:alert(1)'),dict(ok,url='https://evil.example/a"><script>'),dict(ok,url='https://u@voe.sx/e/x'),dict(ok,episode='https://evil.example/a/1/'),
             dict(ok,name='<img src=x>'),dict(ok,devices=1),dict(ok,devices='9'),dict(ok,first='hoy'),'texto',dict(ok)]
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'dead-reports.json').write_text(json.dumps({'checkedAt':'2026-11-17T00:00:00Z','links':[ok]+bad}))
            got=json.loads(owner_files.build(d)['owner/dead-reports.json'])
            self.assertEqual(got['links'],[dict(ok,family='voe')]);self.assertEqual(got['checkedAt'],'2026-11-17T00:00:00Z')
            (d/'dead-reports.json').write_text('{roto');self.assertNotIn('owner/dead-reports.json',owner_files.build(d))
    def test_jk_copy_checked(self):
        """17/11 (Robin): the PC copy summary reaches the owner's editor only with clean fields."""
        good={'schema':1,'builtAt':'2026-11-17T09:00:00.000Z','round':{'startedAt':'2026-11-17T07:55:12.418Z','updatedAt':'2026-11-17T08:32:44.825Z','finished':True,'done':5004,'total':5051,'refreshedEpisodes':48},
              'reasons':{'noProviders':752,'redirect':173,'oddList':47,'network':3,'other':0,'raro':9},'redirect':{'recovered':518,'held':174},
              'worst':[{'url':'https://jkanime.net/tribe-cool-crew/','title':'Tribe Cool Crew','count':50,'reason':'noProviders'},{'url':'javascript:alert(1)','title':'x','count':1,'reason':'other'},
                       {'url':'https://jkanime.net/a/','title':'<b>\nx','count':1,'reason':'redirect'},{'url':'https://jkanime.net/b/','title':'B','count':'5','reason':'mal'}]}
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'jk-copy-summary.json').write_text(json.dumps(good))
            got=json.loads(owner_files.build(d)['owner/jk-copy.json'])
            self.assertEqual(got['reasons'],{'noProviders':752,'redirect':173,'oddList':47,'network':3,'other':0})
            self.assertEqual([w['url'] for w in got['worst']],['https://jkanime.net/tribe-cool-crew/','https://jkanime.net/a/']);self.assertEqual(got['worst'][1]['title'],'')
            self.assertEqual(got['round']['done'],5004);self.assertEqual(got['redirect'],{'recovered':518,'held':174})
            (d/'jk-copy-summary.json').write_text('{"schema":2}');self.assertNotIn('owner/jk-copy.json',owner_files.build(d))
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
    def test_popular(self):
        # 14/11: most watched for the owner: JK series and counts only, top 50
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);rows=[{'series':'https://jkanime.net/frieren/','devices':5,'independentNetworks':4,'extra':'x'},{'series':'https://evil.example/','devices':9}]+[{'series':f'https://jkanime.net/s{i}/','devices':1,'independentNetworks':1} for i in range(80)]
            (d/'play-stats.json').write_text(json.dumps({'checkedAt':'2026-11-13T13:11:39Z','minDeviceAgeHours':24,'popular':rows,'options':[{'url':'secret'}]}))
            x=json.loads(owner_files.build(d)['owner/popular.json'])
            self.assertEqual(x['popular'][0],{'series':'https://jkanime.net/frieren/','devices':5,'networks':4});self.assertEqual(len(x['popular']),50)
            self.assertNotIn('evil',json.dumps(x));self.assertNotIn('options',x)
        with tempfile.TemporaryDirectory() as d:self.assertNotIn('owner/popular.json',owner_files.build(d))
    def test_cloud_runs_with_the_cloud_token_only(self):
        import tempfile
        data={'workflow_runs':[{'name':'Capítulos nuevos cada 5 minutos','status':'completed','conclusion':'success','updated_at':'2026-11-10T08:00:00Z','workflow_id':7,'html_url':'https://github.com/x','actor':{'login':'secret-ish'}}]}
        with tempfile.TemporaryDirectory() as d:
            out=owner_files.build(d,token='t',fetch=lambda url:data)
            runs=json.loads(out['owner/cloud-runs.json'])['workflow_runs'];self.assertEqual(runs[0]['name'],'Capítulos nuevos cada 5 minutos');self.assertNotIn('actor',runs[0])
            self.assertNotIn('owner/cloud-runs.json',owner_files.build(d,token=''))
            def boom(url):raise OSError('offline')
            self.assertNotIn('owner/cloud-runs.json',owner_files.build(d,token='t',fetch=boom))
    def test_backup_in_semaforo(self):
        # 16/11 (mejora A): latest Supabase copy run and latest good one, states and dates only
        data={'workflow_runs':[{'status':'completed','conclusion':'failure','updated_at':'2026-11-16T03:20:00Z','event':'schedule','html_url':'x','actor':{'login':'y'}},
                               {'status':'completed','conclusion':'success','updated_at':'2026-11-13T19:41:00Z','event':'workflow_dispatch'}]}
        with tempfile.TemporaryDirectory() as d:
            x=json.loads(owner_files.build(d,token='t',fetch=lambda url:data)['owner/semaforo.json'])
            self.assertEqual(x['backup'],{'latest':{'status':'completed','conclusion':'failure','updated_at':'2026-11-16T03:20:00Z','event':'schedule'},'lastOkAt':'2026-11-13T19:41:00Z'})
            self.assertNotIn('backup',json.loads(owner_files.build(d,token='')['owner/semaforo.json']))
            def boom(url):raise OSError('offline')
            self.assertNotIn('backup',json.loads(owner_files.build(d,token='t',fetch=boom)['owner/semaforo.json']))
            x=json.loads(owner_files.build(d,token='t',fetch=lambda url:{'workflow_runs':[]})['owner/semaforo.json'])
            self.assertEqual(x['backup'],{'latest':None,'lastOkAt':None})
if __name__=='__main__':unittest.main()
