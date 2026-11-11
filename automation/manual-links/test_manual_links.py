import unittest
from manual_links import classify,update,report
class T(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(classify(404,''),'dead');self.assertEqual(classify(410,''),'dead')
        self.assertEqual(classify(200,'<h1>File was deleted</h1>'),'dead');self.assertEqual(classify(200,'<video>'),'ok')
        self.assertEqual(classify(200,'<div data-pac="file not found">ok</div><script>x="video not found"</script>'),'ok')
        self.assertEqual(classify(0,''),'unknown');self.assertEqual(classify(503,''),'unknown');self.assertEqual(classify(403,''),'unknown')
    def test_two_days_and_timeouts_do_not_reset(self):
        m,d=update({},{'a':'dead','b':'ok'});self.assertEqual(d,set())
        m,d=update(m,{'a':'unknown'});self.assertEqual(d,set());self.assertEqual(m,{'a':1})
        m,d=update(m,{'a':'dead'});self.assertEqual(d,{'a'})
        m,d=update(m,{'a':'ok'});self.assertEqual(d,set());self.assertEqual(m,{})
    def test_report(self):
        r=report([{'title':'B','links':['x','y']},{'title':'A','links':['z']}],{'x'})
        self.assertIn('**B** (1 de 2)',r);self.assertNotIn('**A**',r)
        # S-03: the public issue names the server, never the link itself.
        r=report([{'title':'C','links':['https://powvideo.net/e/abc123']}],{'https://powvideo.net/e/abc123'})
        self.assertIn('powvideo.net',r);self.assertNotIn('abc123',r);self.assertNotIn('https://',r)
    def test_fichas_read_with_cloud_key_and_fail_visibly(self):
        import json,manual_links as m
        cat=json.dumps({'items':[{'id':'a'},{'id':'b'},{'id':'c'}]})
        ficha=lambda t,u:json.dumps({'body':{'title':t,'episodes':[{'options':[{'url':u}]}]}})
        def editor(answers):
            calls=[];left={k:list(v) for k,v in answers.items()}
            def get(path):calls.append(path);a=left[path];return a.pop(0) if len(a)>1 else a[0]
            return get,calls
        waits=[]
        get,calls=editor({'/api/catalogue':[(200,cat)],'/api/titles/a':[(429,'{"error":"slow_down","retry":true}'),(200,ficha('A','https://x/1'))],
                          '/api/titles/b':[(200,ficha('B','https://x/2'))],'/api/titles/c':[(404,'{"error":"not_found"}')]})
        out=m.fichas(get,'k',waits.append)
        self.assertEqual([(f['title'],f['links']) for f in out],[('A',['https://x/1']),('B',['https://x/2'])])
        self.assertEqual(calls.count('/api/titles/a'),2);self.assertIn(m.SLOW_DOWN_WAIT,waits);self.assertEqual(waits.count(m.TITLE_PAUSE),2)
        # Session refused (the 9/11 failure: «0 fichas, all fine»): now it stops, and the memory is not touched.
        get,_=editor({'/api/catalogue':[(200,cat)],'/api/titles/a':[(401,'{"error":"login"}')],'/api/titles/b':[(401,'{"error":"login"}')],'/api/titles/c':[(200,ficha('C','u'))]})
        with self.assertRaises(SystemExit) as e:m.fichas(get,'k',lambda s:None)
        self.assertIn('2 de 3',str(e.exception.code))
        get,_=editor({'/api/catalogue':[(200,cat)],'/api/titles/a':[(429,'{"error":"daily_limit"}')],'/api/titles/b':[(200,ficha('B','u'))],'/api/titles/c':[(200,ficha('C','u'))]})
        with self.assertRaises(SystemExit):m.fichas(get,'k',lambda s:None)
        with self.assertRaises(SystemExit) as e:m.fichas(None,'')
        self.assertIn('ZZ_EDITOR_CLOUD_KEY',str(e.exception.code))
    def test_cloud_key_only_goes_to_the_editor(self):
        import manual_links as m,urllib.request
        seen=[]
        def fake(req,timeout):seen.append(req);raise OSError('offline')
        # quinta revisión S-05: both the editor read and the provider check go through the no-redirect opener.
        try:
            m.NO_REDIRECT.open=fake;m.editor_get('/api/catalogue','k-1');m.fetch('https://provider.example/e/1')
        finally:del m.NO_REDIRECT.open
        self.assertEqual(seen[0].get_header('X-zz-cloud'),'k-1');self.assertTrue(seen[0].full_url.startswith(m.EDITOR+'/'))
        self.assertIsNone(seen[1].get_header('X-zz-cloud'));self.assertEqual(len(seen),2)
if __name__=='__main__':unittest.main()
