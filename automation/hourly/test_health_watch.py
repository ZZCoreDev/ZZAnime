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
if __name__=='__main__':unittest.main()
