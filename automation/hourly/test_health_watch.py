"""Health watchdog: each alarm from synthetic provider-data, and one issue per kind (open, update, close)."""
import datetime,gzip,hashlib,json,tempfile,unittest
from pathlib import Path
import health_watch as h
NOW=datetime.datetime(2026,11,1,12,tzinfo=datetime.timezone.utc).timestamp()
def iso(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat()
def put(folder,name,value,raw=False):
    p=Path(folder)/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value if raw else json.dumps(value).encode())
def healthy(folder,indexBytes=1200000):
    url='https://jkanime.net/a/1/';shard=gzip.compress(json.dumps({'episodes':[{'url':url}]}).encode())
    put(folder,'published-assets/series/s.bin',shard,True);put(folder,'published-assets/indexes/i.bin',{'series':{'x':{'path':'series/s.bin'}}})
    put(folder,'published-assets/channel.json',{'payload':json.dumps({'indexPath':'indexes/i.bin','indexBytes':indexBytes}),'signature':'0'})
    put(folder,'publication.json',{'publishedAt':iso(NOW-600)});put(folder,'news-watchdog.json',{'attemptedAt':iso(NOW-300),'state':'complete'})
    put(folder,'renewal-history.json',[{'start':NOW-i*900,'renewed':100,'published':True} for i in range(3)]);put(folder,'renewal-status.json',{'failed':1000,'state':'complete'})
    put(folder,'link-health.json',{'last':{'checkedAt':NOW-600},'links':{}});put(folder,'help-status.json',{'worker':{'today':{'requests':4}}})
    put(folder,'observations.json',{'newsSeen':{url:iso(NOW-5*3600)}})
class HealthWatchTests(unittest.TestCase):
    def failing(self,folder,memory=None,now=NOW):
        r,m=h.check(folder,now,memory or {});return sorted(k for k,(f,_,_) in r.items() if f),m
    def test_healthy_data_raises_nothing_but_secrets_are_dated(self):
        with tempfile.TemporaryDirectory() as d:
            healthy(d);self.assertEqual(self.failing(d)[0],[])
            later=datetime.datetime(2027,1,1,tzinfo=datetime.timezone.utc).timestamp()
            r,_=h.check(d,later,{});self.assertTrue(r['secreto-GH_DISPATCH_TOKEN'][0]);self.assertFalse(r['secreto-ZZ_CLOUDFLARE_TOKEN'][0])
    def test_each_alarm(self):
        with tempfile.TemporaryDirectory() as d:
            healthy(d);put(d,'publication.json',{'publishedAt':iso(NOW-4*3600)});self.assertIn('noticias',self.failing(d)[0])
            healthy(d);put(d,'renewal-history.json',[{'start':NOW-i*900,'renewed':0,'published':True} for i in range(3)]);self.assertIn('renovacion',self.failing(d)[0])
            healthy(d,indexBytes=1900000);self.assertIn('indice',self.failing(d)[0])
            healthy(d);put(d,'link-health.json',{'last':{'checkedAt':NOW-4*3600}});self.assertIn('enlaces',self.failing(d)[0])
            healthy(d);put(d,'playback-probe.json',{'families':{'voe':{'failingDays':2},'mega':{'failingDays':1}}})
            f=self.failing(d)[0];self.assertIn('reproduccion-voe',f);self.assertNotIn('reproduccion-mega',f)
            Path(d,'published-assets/channel.json').unlink();self.assertEqual(self.failing(d)[0],['datos'])
    def test_news_with_options_missing_from_channel_but_not_voe_only(self):
        with tempfile.TemporaryDirectory() as d:
            healthy(d);url='https://jkanime.net/b/2/';parent='https://jkanime.net/b/'
            put(d,'observations.json',{'newsSeen':{url:iso(NOW-4*3600)}})
            def shard(providers):put(d,'series-state/'+hashlib.sha256(parent.encode()).hexdigest()+'.json.gz',gzip.compress(json.dumps({'episodes':{url:{'providers':providers}}}).encode()),True)
            shard([{'name':'Voe','family':'voe','links':['https://voe.sx/e/x']}]);self.assertEqual(self.failing(d)[0],[])
            shard([{'name':'Mp4upload','family':'mp4upload','links':['https://www.mp4upload.com/embed-x.html']}]);self.assertEqual(self.failing(d)[0],['noticias'])
            key=hashlib.sha256(('Mp4upload\0https://www.mp4upload.com/embed-x.html').encode()).hexdigest()
            put(d,'link-health.json',{'last':{'checkedAt':NOW-600},'links':{key:{'excluded':True}}});self.assertEqual(self.failing(d)[0],[])
    def test_failed_rise_and_quiet_worker_use_memory(self):
        with tempfile.TemporaryDirectory() as d:
            healthy(d);DAY=86400
            put(d,'renewal-status.json',{'failed':1049});self.assertNotIn('fallos',self.failing(d,{'failed':[[NOW-DAY,1000]]})[0])
            put(d,'renewal-status.json',{'failed':1051});self.assertIn('fallos',self.failing(d,{'failed':[[NOW-DAY,1000]]})[0])
            self.assertNotIn('fallos',self.failing(d,{})[0])
            put(d,'help-status.json',{'worker':{'today':{'requests':0}}})
            f,m=self.failing(d,{'workerRequestsAt':NOW-25*3600});self.assertIn('worker',f)
            f,m=self.failing(d,{});self.assertNotIn('worker',f);self.assertIn('worker',self.failing(d,m,NOW+25*3600)[0])
    def test_new_bans_warn_for_24h_and_unreadable_report(self):
        with tempfile.TemporaryDirectory() as d:
            healthy(d);HOUR=3600
            r,m=h.check(d,NOW,{},{'schema':1,'cap':300,'bans':[],'bannedDevices':0,'deviceBans':[]})
            self.assertFalse(r['bloqueos'][0]);self.assertFalse(r['informe-tope'][0])
            ban={'schema':1,'cap':300,'bans':[{'user':'0123456789abcdef-uuid','at':iso(NOW-60)}],'bannedDevices':1,'deviceBans':[{'at':iso(NOW-60)}]}
            r,m=h.check(d,NOW+HOUR,m,ban);self.assertTrue(r['bloqueos'][0]);body=r['bloqueos'][2]
            self.assertIn('Cuenta 01234567…',body);self.assertNotIn('89abcdef',body,'public issue: id cut');self.assertIn('Aparato',body);self.assertIn('(2)',body)
            # Same bans seen again are not new; listed for 24 h; the device ban stays in the report a year and never counts again.
            r,m=h.check(d,NOW+2*HOUR,m,ban);self.assertIn('(2)',r['bloqueos'][2])
            noacc={**ban,'bans':[]}
            r,m=h.check(d,NOW+23*HOUR,m,noacc);self.assertTrue(r['bloqueos'][0])
            r,m=h.check(d,NOW+26*HOUR,m,noacc);self.assertFalse(r['bloqueos'][0])
            r,m=h.check(d,NOW+9*86400,m,noacc);self.assertFalse(r['bloqueos'][0]);self.assertEqual(list(m['bans']),['Aparato (series)|'+iso(NOW-60)])
            # A second account later reopens it with only the new one.
            r,m=h.check(d,NOW+10*86400,m,{**noacc,'bans':[{'user':'fedcba98-x','at':iso(NOW+10*86400-30)}]})
            self.assertTrue(r['bloqueos'][0]);self.assertIn('(1)',r['bloqueos'][2]);self.assertIn('fedcba98',r['bloqueos'][2])
            # Report unreadable (Worker down, wrong key): warned after 6 h; without the key nothing is checked.
            r,m=h.check(d,NOW+10*86400+5*HOUR,m,None);self.assertFalse(r['informe-tope'][0]);self.assertNotIn('bloqueos',r)
            r,m=h.check(d,NOW+10*86400+7*HOUR,m,{'error':'owner'});self.assertTrue(r['informe-tope'][0])
            r,_=h.check(d,NOW,{});self.assertNotIn('bloqueos',r);self.assertNotIn('informe-tope',r)
    def test_editor_bans_join_channel_bans(self):
        with tempfile.TemporaryDirectory() as d:
            healthy(d);HOUR=3600
            empty={'schema':1,'cap':300,'bans':[],'bannedDevices':0,'deviceBans':[]}
            ed={**empty,'bans':[{'user':'abcdef0123-uuid','at':iso(NOW-30)}],'bannedDevices':1,'deviceBans':[{'at':iso(NOW-30)}]}
            r,m=h.check(d,NOW,{},empty,ed);body=r['bloqueos'][2]
            self.assertTrue(r['bloqueos'][0]);self.assertIn('Cuenta abcdef01… (fichas del editor)',body);self.assertIn('Aparato (fichas del editor)',body)
            self.assertIn('editor: 1 cuentas y 1 aparatos (tope 300 fichas',body);self.assertIn('canal: 0 cuentas',body)
            # Editor report unreadable for a while: its known bans are kept, so they are not new again when it comes back.
            r,m=h.check(d,NOW+8*86400,m,empty,None);self.assertTrue(r['informe-tope'][0]);self.assertIn('- editor:',r['informe-tope'][2]);self.assertNotIn('- canal:',r['informe-tope'][2])
            r,m=h.check(d,NOW+8*86400+HOUR,m,empty,ed);self.assertFalse(r['bloqueos'][0]);self.assertFalse(r['informe-tope'][0])
            # Only the editor checked (no channel key): fine too.
            r,_=h.check(d,NOW,{},False,ed);self.assertTrue(r['bloqueos'][0]);self.assertNotIn('canal:',r['bloqueos'][2])
    def test_fetch_quota_sends_cloud_key_and_survives_errors(self):
        import io,urllib.error,urllib.request
        seen=[];real=urllib.request.urlopen
        class Answer(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*a):return False
        try:
            urllib.request.urlopen=lambda req,timeout:(seen.append(req),Answer(b'{"schema":1,"bans":[]}'))[1]
            self.assertEqual(h.fetch_quota('k-123'),{'schema':1,'bans':[]})
            self.assertEqual(seen[0].get_header('X-zz-cloud'),'k-123');self.assertEqual(seen[0].full_url,h.QUOTA_URL)
            def fail(req,timeout):raise urllib.error.HTTPError(h.QUOTA_URL,403,'Forbidden',{},None)
            urllib.request.urlopen=fail;self.assertIsNone(h.fetch_quota('k-123'))
        finally:urllib.request.urlopen=real
    def test_one_issue_per_kind_updated_and_closed(self):
        class Fake:
            def __init__(self):self.issues=[];self.calls=[]
            def call(self,method,path,body=None):
                self.calls.append((method,path))
                if path=='/labels':return {}
                if method=='GET':return [i for i in self.issues if i['state']=='open']
                if method=='POST' and path=='/issues':self.issues.append({'number':len(self.issues)+1,'state':'open',**body});return {}
                n=int(path.split('/')[2])
                if method=='PATCH':self.issues[n-1].update(body)
                return {}
        g=Fake();fail={'indice':(True,'Índice grande','indexBytes=1900000'),'enlaces':(False,'ok','')}
        self.assertEqual(h.sync(g,fail,NOW),[('open','indice')]);self.assertEqual(h.sync(g,fail,NOW+3600),[])
        self.assertEqual(len(g.issues),1);self.assertIn('<!-- vigia:indice -->',g.issues[0]['body'])
        self.assertEqual(h.sync(g,{'indice':(True,'Índice grande','indexBytes=1950000')},NOW),[('update','indice')])
        self.assertEqual(h.sync(g,{'indice':(False,'ok','')},NOW),[('close','indice')]);self.assertEqual(g.issues[0]['state'],'closed')
        self.assertEqual(h.sync(g,{'indice':(False,'ok','')},NOW),[])
        self.assertEqual(g.calls.count(('POST','/issues/1/comments')),1,'only the closing comment: plain updates send none')
        # A new ban updates the open «bloqueos» issue and also comments, so GitHub mails it.
        h.sync(g,{'bloqueos':(True,'Bloqueos','- Cuenta a')},NOW);h.sync(g,{'bloqueos':(True,'Bloqueos','- Cuenta a\n- Cuenta b')},NOW)
        self.assertEqual(g.calls[-1],('POST','/issues/2/comments'))
if __name__=='__main__':unittest.main()
