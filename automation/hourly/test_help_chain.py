"""Help chain (task 10): synthetic fixtures only; no provider, Worker or source requests."""
import copy,datetime,gzip,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
import help_chain as h
import run

TRIAL=['https://jkanime.net/tokyo-revengers-santen-sensou-hen/5/','https://jkanime.net/steel-ball-run-jojo-no-kimyou-na-bouken/7/']
def iso(t):return t.isoformat().replace('+00:00','Z')
def fixture(now):
 # Series A has an approved option; B and C are fresh news without any option; D is news older than 7 days.
 a,b,c,d=('https://jkanime.net/'+s for s in ['serie-a/3/','tokyo-revengers-santen-sensou-hen/5/','steel-ball-run-jojo-no-kimyou-na-bouken/7/','serie-d/2/'])
 link='https://www.mp4upload.com/embed-a.html'
 state={'episodes':{a:{'episode':a,'complete':True,'observedAt':iso(now),'providers':[{'name':'Mp4upload','family':'mp4upload','links':[link]}]}},
  'listings':{'https://jkanime.net/serie-a/':{'complete':True,'observedAt':iso(now),'episodes':[a]},'https://jkanime.net/tokyo-revengers-santen-sensou-hen/':{'complete':True,'observedAt':'2026-10-27T08:29:59.953Z','episodes':[b]}},
  'newsSeen':{a:iso(now),b:iso(now-datetime.timedelta(hours=1)),c:iso(now-datetime.timedelta(hours=2)),d:iso(now-datetime.timedelta(days=8))},'pending':[]}
 return state,{run.sha(('Mp4upload\0'+link).encode()):True},(a,b,c,d)
STATS={'today':{'devices':3},'quorum':{'sameNetworkOnly':1}}
def worker(path):return {'/v1/stats':{'schema':1,**STATS},'/v1/dead-reports':{'schema':1,'links':[{'episode':'https://jkanime.net/x/1/','name':'Mega','family':'mega','url':'https://mega.nz/file/AbCd1234#'+'K'*43,'devices':2}]}}[path]
def answer(now,episode,**option):
 o={'name':'Mega','family':'mega','url':'https://mega.nz/file/AbCdEfGh#'+'k'*43,'devices':2,'asns':2,'check':'name-match',**option}
 return {'schema':1,'episodes':[{'url':episode,'acceptedAt':iso(now),'firstSeenAt':iso(now-datetime.timedelta(hours=1)),'options':[o]}]}

class WantedTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime.datetime.now(datetime.timezone.utc);self.state,self.approved,self.urls=fixture(self.now)
  _,self.files=run.build(self.state,self.approved,self.now)
 def rules(self,mode):return {'mode':mode,'trial':TRIAL,'max':40}
 def test_open_lists_only_fresh_chapters_without_options(self):
  a,b,c,d=self.urls;w=h.wanted(self.state,self.files,self.now,self.rules('open'),{})
  self.assertEqual([x['url'] for x in w],[b,c]);self.assertEqual(w[0]['number'],5)
 def test_off_publishes_nothing_and_trial_keeps_two(self):
  self.assertIsNone(h.wanted(self.state,self.files,self.now,self.rules('off'),{}))
  self.state['newsSeen']['https://jkanime.net/otra/1/']=iso(self.now)
  self.assertEqual({x['url'] for x in h.wanted(self.state,self.files,self.now,self.rules('trial'),{})},set(TRIAL))
 def test_chapter_drops_out_once_it_has_options(self):
  a,b,c,d=self.urls;self.state['episodes'][b]={'episode':b,'complete':True,'observedAt':iso(self.now),'providers':[{'name':'Mp4upload','family':'mp4upload','links':['https://www.mp4upload.com/embed-a.html']}]}
  _,files=run.build(self.state,self.approved,self.now)
  self.assertNotIn(b,[x['url'] for x in h.wanted(self.state,files,self.now,self.rules('open'),{})])
 def test_policy_rejects_bad_trial(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d,'p.json');p.write_text(json.dumps({'mode':'trial','trial':TRIAL[:1]}))
   with self.assertRaises(ValueError):h.policy(p)
   p.write_text(json.dumps({'mode':'open','maxWanted':500}));self.assertEqual(h.policy(p)['max'],40)
   self.assertEqual(h.policy(Path(d,'missing.json'))['mode'],'off')
 def test_shipped_policy_asks_new_chapters_and_renewal(self):
  # Open with renewal (Robin, 31/10): every missing new chapter plus the oldest observations.
  self.assertEqual(h.policy(),{'mode':'open','trial':TRIAL,'max':40,'renew':180,'held':100})
 def test_open_mode_renews_oldest_published_chapters(self):
  a,b,c,d=self.urls;old=self.now-datetime.timedelta(days=30)
  for i in range(3):
   u='https://jkanime.net/serie-a/'+str(10+i)+'/';self.state['episodes'][u]={'episode':u,'complete':True,'observedAt':h.iso(old+datetime.timedelta(days=i)),'providers':[{'name':'Mp4upload','family':'mp4upload','links':['https://www.mp4upload.com/embed-a.html']}]};self.state['listings']['https://jkanime.net/serie-a/']['episodes'].append(u)
  _,files=run.build(self.state,self.approved,self.now)
  w=h.wanted(self.state,files,self.now,{'mode':'open','trial':TRIAL,'max':40,'renew':2},{})
  self.assertEqual([(x['url'],x.get('renew',False)) for x in w],[(b,False),(c,False),('https://jkanime.net/serie-a/10/',True),('https://jkanime.net/serie-a/11/',True)])
  self.assertNotIn(a,[x['url'] for x in w])  # observed today: not due for renewal
  self.assertEqual([x['url'] for x in h.wanted(self.state,files,self.now,self.rules('trial'),{})],[b,c])
 def test_wanted_list_stays_far_below_the_64kb_channel_limit(self):
  base='https://jkanime.net/serie-a/';old=h.iso(self.now-datetime.timedelta(days=9))
  for i in range(400):
   u=base+str(100+i)+'/';self.state['episodes'][u]={'episode':u,'complete':True,'observedAt':old,'providers':[{'name':'Mp4upload','family':'mp4upload','links':['https://www.mp4upload.com/embed-a.html']}]};self.state['listings'][base]['episodes'].append(u)
  _,files=run.build(self.state,self.approved,self.now)
  w=h.wanted(self.state,files,self.now,{'mode':'open','trial':TRIAL,'max':40,'renew':180},{u.rsplit('/',2)[0]+'/':'T'*60 for u in self.state['episodes']})
  self.assertLessEqual(len(json.dumps(w,ensure_ascii=False,separators=(',',':')).encode()),h.WANTED_BYTES);self.assertGreater(len(w),100)

 def test_held_batches_go_after_news_before_renewal_and_rotate_daily(self):
  # Fixed day for the whole test (fixture included): the daily rotation must not depend on when CI runs.
  self.now=datetime.datetime(2026,11,1,12,tzinfo=datetime.timezone.utc);self.state,self.approved,self.urls=fixture(self.now)
  a,b,c,d=self.urls;old=self.now-datetime.timedelta(days=30)
  u='https://jkanime.net/serie-a/10/';self.state['episodes'][u]={'episode':u,'complete':True,'observedAt':h.iso(old),'providers':[{'name':'Mp4upload','family':'mp4upload','links':['https://www.mp4upload.com/embed-a.html']}]};self.state['listings']['https://jkanime.net/serie-a/']['episodes'].append(u)
  _,files=run.build(self.state,self.approved,self.now)
  held=['https://jkanime.net/ova-%d/1/'%i for i in range(5)]+[a]
  rules={'mode':'open','trial':TRIAL,'max':40,'renew':2,'held':2}
  day=self.now
  w=h.wanted(self.state,files,day,rules,{},held)
  first=[x['url'] for x in w if 'ova-' in x['url']];self.assertEqual(len(first),2)
  self.assertEqual([x['url'] for x in w[:2]],[b,c]);self.assertTrue(w[-1].get('renew'));self.assertFalse(any(x.get('renew') for x in w[:4]))
  self.assertNotIn(a,[x['url'] for x in w]);self.assertEqual(w[2]['held'],True);self.assertEqual(set(w[2]),{'url','number','title','held'})
  days=[[x['url'] for x in h.wanted(self.state,files,day+datetime.timedelta(days=n),rules,{},held) if 'ova-' in x['url']] for n in range(3)]
  self.assertEqual(sorted(sum(days,[])),sorted(held[:5]))
  self.assertFalse(any('ova-' in x['url'] for x in h.wanted(self.state,files,day,{**rules,'held':0},{},held)))
  self.assertFalse(any('ova-' in x['url'] for x in h.wanted(self.state,files,day,{**rules,'mode':'trial'},{},held)))
 def test_shipped_held_list_is_466_chapter_ones_in_the_catalogue(self):
  urls=h.held_chapters();cat=h.titles()
  self.assertEqual(len(urls),466);self.assertEqual(len(set(urls)),466)
  self.assertTrue(all(u.endswith('/1/') and u.rsplit('/',2)[0]+'/' in cat for u in urls))

class RetryTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime.datetime.now(datetime.timezone.utc);self.state,_,self.urls=fixture(self.now)
 def test_only_asked_chapters(self):
  _,b,c,_=self.urls
  candidates,held=h.retry_candidates(answer(self.now,c),self.state,{b},self.now)
  self.assertEqual(candidates,set());self.assertIn(c,held)
 def test_quorum_and_check_rules(self):
  b=self.urls[1]
  for bad in [{'devices':1},{'asns':1},{'check':'none'},{'check':'quorum3','asns':2},{'url':'http://mega.nz/x'},{'devices':'2'}]:
   with self.subTest(bad=bad):self.assertEqual(h.retry_candidates(answer(self.now,b,**bad),self.state,{b},self.now)[0],set())
  self.assertEqual(h.retry_candidates(answer(self.now,b,check='quorum3',asns=3),self.state,{b},self.now)[0],{b})
 def test_renewal_suggestion_preserves_the_old_record(self):
  a=self.urls[0]
  self.state['episodes'][a]['observedAt']=h.iso(self.now-datetime.timedelta(days=9))
  before=copy.deepcopy(self.state)
  with tempfile.TemporaryDirectory() as folder:
   folder=Path(folder);h.record_published(folder,[{'url':a,'renew':True}],self.now)
   with patch.dict('os.environ',{'ZZ_HELP_URL':'https://help.invalid','ZZ_HELP_KEY':'k'}),patch.object(h,'save_observations') as save:
    report=h.pull(folder,self.state,self.now,fetch=lambda:answer(self.now,a),observe_fetch=worker)
   save.assert_not_called()
  self.assertEqual((report['imported'],report['queued']),(0,0))
  self.assertEqual(self.state,before)
 def test_stale_or_future_acceptance_is_held(self):
  b=self.urls[1]
  for t in [self.now-datetime.timedelta(days=8),self.now+datetime.timedelta(hours=1)]:
   self.assertEqual(h.retry_candidates(answer(t,b),self.state,{b},self.now)[0],set())
 def test_pull_saves_only_missing_chapter_ids_and_does_not_duplicate_them(self):
  from archive_state import load,save
  a,b,c,d=self.urls
  self.state['pending']=[d]
  data={'schema':1,'episodes':sum((answer(self.now,u)['episodes'] for u in (a,b,c,b)),[])}
  before=copy.deepcopy(self.state)
  with tempfile.TemporaryDirectory() as folder:
   folder=Path(folder);save(folder,self.state)
   h.record_published(folder,[{'url':a,'renew':True},{'url':b},{'url':c,'held':True}],self.now)
   original={p.name:p.read_bytes() for p in (folder/'series-state').glob('*.json.gz')}
   with patch.dict('os.environ',{'ZZ_HELP_URL':'https://help.invalid','ZZ_HELP_KEY':'k'}):
    report=h.pull(folder,self.state,self.now,fetch=lambda:data,observe_fetch=worker)
    self.assertEqual((report['state'],report['imported'],report['queued']),('queued',0,2))
    second=h.pull(folder,self.state,self.now,fetch=lambda:data,observe_fetch=worker)
    self.assertEqual((second['state'],second['queued']),('unchanged',0))
   self.assertEqual(load(folder)['pending'],[d,*sorted([b,c])])
   self.assertEqual({p.name:p.read_bytes() for p in (folder/'series-state').glob('*.json.gz')},original)
  self.assertEqual(self.state,{**before,'pending':[d,*sorted([b,c])]})
 def test_key_derives_from_collector_secret(self):
  import hmac,hashlib
  self.assertEqual(h.derived('help-key','s'),hmac.new(b's',b'zzanime-ayuda/help-key',hashlib.sha256).hexdigest());self.assertEqual(h.derived('help-key',''),'')
  self.assertNotEqual(h.derived('help-key','s'),h.derived('salt','s'))
 def test_disabled_makes_no_request_and_nothing_asked_only_observes(self):
  with tempfile.TemporaryDirectory() as folder:
   def fail(*a):raise AssertionError('no request expected')
   with patch.dict('os.environ',{},clear=True):self.assertEqual(h.pull(Path(folder),self.state,self.now,fetch=fail,observe_fetch=fail)['state'],'disabled')
   with patch.dict('os.environ',{'ZZ_HELP_URL':'https://help.invalid','ZZ_HELP_KEY':'k'}):r=h.pull(Path(folder),self.state,self.now,fetch=fail,observe_fetch=worker)
   self.assertEqual((r['state'],r['worker']['today']['devices'],r['deadReports']),('nothing-asked',3,1))
   self.assertEqual(json.loads(Path(folder,'dead-reports.json').read_bytes())['links'][0]['family'],'mega')
 def test_worker_summary_and_reports_never_block_queuing(self):
  b=self.urls[1]
  with tempfile.TemporaryDirectory() as folder:
   folder=Path(folder);h.record_published(folder,[{'url':b}],self.now)
   def down(path):raise OSError('worker down')
   with patch.dict('os.environ',{'ZZ_HELP_URL':'https://help.invalid','ZZ_HELP_KEY':'k'}),patch.object(h,'save_observations'):
    report=h.pull(folder,self.state,self.now,fetch=lambda:answer(self.now,b),observe_fetch=down)
   self.assertEqual(report['queued'],1);self.assertIn('worker down',report['worker']['error'])
   self.assertIsNone(report['deadReports']);self.assertFalse(Path(folder,'dead-reports.json').exists())
 def test_same_network_answers_need_three_zones_and_the_file_name(self):
  b=self.urls[1]
  for bad in [{'asns':1,'zones':2,'devices':3},{'asns':1,'zones':3,'devices':2},{'asns':1,'zones':3,'devices':3,'check':'quorum3'}]:
   with self.subTest(bad=bad):self.assertEqual(h.retry_candidates(answer(self.now,b,**bad),self.state,{b},self.now)[0],set())
  self.assertEqual(h.retry_candidates(answer(self.now,b,asns=1,zones=3,devices=3),self.state,{b},self.now)[0],{b})

class RunIntegrationTests(unittest.TestCase):
 def test_two_confirmed_series_reach_the_signed_channel_with_their_own_options(self):
  from archive_state import load,save
  now=datetime.datetime.now(datetime.timezone.utc);state,_,(a,b,c,_)=fixture(now)
  state['newsSeen'].pop(b)
  state['newsSeen'].pop(c)
  state['episodes'][a]['observedAt']=iso(now-datetime.timedelta(days=9))
  existing_links=state['episodes'][a]['providers'][0]['links']
  existing_links.append('https://www.mp4upload.com/embed-a-backup.html')
  trusted={b:'https://www.mp4upload.com/embed-b.html',c:'https://www.mp4upload.com/embed-c.html'}
  parents={u:u.rsplit('/',2)[0]+'/' for u in trusted}
  episode=lambda u,v:{'episode':u,'complete':True,'observedAt':iso(now),'providers':[{'name':'Mp4upload','family':'mp4upload','links':[v]}]}
  listings={parent:{'series':parent,'complete':True,'observedAt':iso(now),'episodes':[u]} for u,parent in parents.items()}
  state['episodes'][b]={**episode(b,trusted[b]),'observedAt':iso(now-datetime.timedelta(seconds=1)),'complete':False,'providers':[]}
  state['listings'][parents[b]]=listings[parents[b]]
  empty={'episodes':{},'listings':{},'pending':[]}
  confirmed={'episodes':{u:episode(u,v) for u,v in trusted.items()},'listings':listings,'pending':[]}
  partial={'episodes':{b:{**episode(b,trusted[b]),'complete':False},c:episode(c,'https://provider.invalid/embed-c.html')},'listings':listings,'pending':[]}
  data={'schema':1,'episodes':answer(now,b)['episodes']+answer(now,c)['episodes']}
  requests=[]
  def collect(req,**kwargs):
   request=json.loads(req.data);requests.append(request)
   result={'passed':True,'primary':'unavailable','errors':{},'recent':[],'state':empty}
   if len(requests)==2:result['state']=partial
   if len(requests)==4:result['state']=confirmed
   from io import BytesIO
   return BytesIO(json.dumps(result).encode())
  def help_inbox(base,key,path):
   return data if path=='/v1/accepted' else worker(path)
  written={}
  put=run.put
  def keep_assets(path,body):
   if path.parent.name=='series':written[path.name]=body
   return put(path,body)
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);save(folder,state)
   h.record_published(folder,[{'url':u} for u in trusted],now)
   env={'ZZ_COLLECTOR_URL':'https://collector.invalid','ZZ_COLLECTOR_KEY':'test-only','ZZ_HELP_URL':'https://help.invalid','ZZ_HELP_KEY':'k','ZZ_PROOF':'false','ZZ_SIGNING_KEY':''}
   with patch.object(run,'D',folder),patch.object(run,'COLLECTION_BATCHES',1),patch('run.NO_REDIRECT.open',side_effect=collect),patch.object(h,'get',side_effect=help_inbox),patch.object(h,'held_chapters',return_value=[c]),patch.dict('os.environ',env,clear=False),patch('sys.argv',['run.py','--news-only','--collect']),patch.object(run,'put',side_effect=keep_assets):
    run.main()
    self.assertFalse((folder/'verification.json').exists())
    self.assertEqual(set(load(folder)['pending']),set(trusted))
    self.assertEqual(load(folder)['episodes'],state['episodes'])
    run.main()
    self.assertFalse((folder/'verification.json').exists())
    self.assertEqual(set(load(folder)['pending']),set(trusted))
    self.assertEqual(load(folder)['episodes'],state['episodes'])
    run.main()
    self.assertEqual(requests[2]['retry'],[])
    self.assertTrue(set(trusted).issubset(requests[2]['skip']))
    saved=load(folder);saved['deferred']={u:0 for u in trusted};save(folder,saved)
    run.main()
   self.assertEqual(requests[0]['retry'],[])
   self.assertEqual(set(requests[1]['retry']),set(trusted))
   self.assertEqual(set(requests[3]['retry']),set(trusted))
   saved=load(folder)
   self.assertEqual(saved['episodes'][a],state['episodes'][a])
   self.assertEqual(saved['pending'],[])
   self.assertIn(b,saved['newsSeen'])
   self.assertNotIn(c,saved['newsSeen'])
   published={row['url']:row for body in written.values() for row in json.loads(gzip.decompress(body))['episodes']}
   self.assertEqual(set(published),{a,b,c})
   self.assertEqual([option['url'] for option in published[a]['options']],existing_links)
   for u,v in trusted.items():
    self.assertEqual(saved['episodes'][u],confirmed['episodes'][u])
    self.assertIn(v,json.dumps(published[u]))
    self.assertNotIn(data['episodes'][0]['options'][0]['url'],json.dumps(published[u]))
   self.assertFalse(json.loads((folder/'verification.json').read_bytes())['published'])

 def test_failing_help_service_never_blocks_a_news_check(self):
  from io import BytesIO
  empty={'passed':True,'primary':'unavailable','errors':{},'recent':[],'state':{'episodes':{},'listings':{},'pending':[]}}
  with tempfile.TemporaryDirectory() as d,patch.object(h,'pull',side_effect=OSError('help down')) as puller,patch.object(run,'D',Path(d)),patch('run.NO_REDIRECT.open',return_value=BytesIO(json.dumps(empty).encode())),patch.dict('os.environ',{'ZZ_COLLECTOR_URL':'https://collector.invalid','ZZ_COLLECTOR_KEY':'test-only','ZZ_HELP_URL':'https://help.invalid'}),patch('sys.argv',['run.py','--news-only','--collect']):
   run.main();puller.assert_called_once()
   self.assertFalse((Path(d)/'verification.json').exists())

class LegacyReaderTests(unittest.TestCase):
 def test_installed_readers_accept_signed_channel_with_wanted(self):
  now=datetime.datetime.now(datetime.timezone.utc);state,approved,urls=fixture(now);key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);public=root/'key.der';public.write_bytes(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))
   index,files=run.build(state,approved,now);body=run.raw(index);digest=run.sha(body);path='indexes/'+digest+'.bin';files[path]=body;results=[]
   wanted=h.wanted(state,files,now,{'mode':'open','trial':TRIAL,'max':40,'held':1},{},['https://jkanime.net/ova-x/1/'])
   cp=run.compile_java(root/'old')
   for extra in [{},{'wanted':wanted}]:
    payload=run.raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':iso(now),'indexSha256':digest,'indexPath':path,'indexBytes':len(body),'mode':'daily-new',**extra})
    site=root/('site'+str(len(results)))
    for n,b in {**files,'channel.json':run.raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})}.items():run.put(site/n,b)
    results.append(json.loads(run.command(['java','-cp',cp,'tv.jkanime.web.CloudVerify',str(site),str(public),str(root/('cache'+str(len(results))))])))
   # Two news plus one held entry carrying the extra "held" key: installed readers give the same result.
   self.assertEqual(len(wanted),3);self.assertEqual(wanted[2].get('held'),True);self.assertEqual(results[0],results[1])

if __name__=='__main__':unittest.main()
