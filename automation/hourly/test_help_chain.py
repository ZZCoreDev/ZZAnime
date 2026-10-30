"""Help chain (task 10): synthetic fixtures only; no provider, Worker or source requests."""
import copy,datetime,json,tempfile,unittest
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
  self.assertEqual(h.policy(),{'mode':'open','trial':TRIAL,'max':40,'renew':180})
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

class AcceptTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime.datetime.now(datetime.timezone.utc);self.state,_,self.urls=fixture(self.now)
 def test_only_asked_chapters(self):
  a,b,c,d=self.urls;incoming,_,held=h.accept(answer(self.now,c),self.state,{b},self.now)
  self.assertEqual(incoming['episodes'],{});self.assertIn(c,held)
 def test_never_replaces_a_stored_record(self):
  a,b,c,d=self.urls;incoming,_,held=h.accept(answer(self.now,a),self.state,{a},self.now)
  self.assertEqual(held[a],'Already stored')
 def test_quorum_and_check_rules(self):
  b=self.urls[1]
  for bad in [{'devices':1},{'asns':1},{'check':'none'},{'check':'quorum3','asns':2},{'family':'unknown'},{'url':'http://mega.nz/x'}]:
   with self.subTest(bad=bad):self.assertEqual(h.accept(answer(self.now,b,**bad),self.state,{b},self.now)[0]['episodes'],{})
  self.assertIn(b,h.accept(answer(self.now,b,check='quorum3',asns=3),self.state,{b},self.now)[0]['episodes'])
 def test_renew_replaces_only_asked_and_older_records(self):
  a=self.urls[0];before=copy.deepcopy(self.state)
  self.assertEqual(h.accept(answer(self.now,a),self.state,{a},self.now)[2][a],'Already stored')
  older=self.now-datetime.timedelta(days=1);self.assertEqual(h.accept(answer(older,a),self.state,{a},self.now,frozenset({a}))[2][a],'Stored observation is newer')
  self.state['episodes'][a]['observedAt']=h.iso(self.now-datetime.timedelta(days=9))
  incoming,seen,held=h.accept(answer(self.now,a),self.state,{a},self.now,frozenset({a}))
  self.assertEqual(incoming['episodes'][a]['providers'][0]['name'],'Mega');self.assertTrue(incoming['episodes'][a]['helpEvidence']['renewed']);self.assertEqual(seen,{})
  with tempfile.TemporaryDirectory() as folder:
   folder=Path(folder);h.record_published(folder,[{'url':a,'renew':True}],self.now)
   with patch.dict('os.environ',{'ZZ_HELP_URL':'https://help.invalid','ZZ_HELP_KEY':'k'}),patch.object(h,'save_observations'):r=h.pull(folder,self.state,self.now,fetch=lambda:answer(self.now,a))
  self.assertEqual((r['imported'],r['renewed']),(1,1));self.assertEqual(self.state['newsSeen'][a],before['newsSeen'][a]);self.assertEqual(self.state['episodes'][a]['observedAt'],h.iso(self.now))
 def test_stale_or_future_acceptance_is_held(self):
  b=self.urls[1]
  for t in [self.now-datetime.timedelta(days=8),self.now+datetime.timedelta(hours=1)]:
   self.assertEqual(h.accept(answer(t,b),self.state,{b},self.now)[0]['episodes'],{})
 def test_pull_keeps_listing_date_and_builds_minimal_listing(self):
  a,b,c,d=self.urls;before=copy.deepcopy(self.state)
  with tempfile.TemporaryDirectory() as folder:
   folder=Path(folder);h.record_published(folder,[{'url':b},{'url':c}],self.now);data={'schema':1,'episodes':answer(self.now,b)['episodes']+answer(self.now,c)['episodes']}
   with patch.dict('os.environ',{'ZZ_HELP_URL':'https://help.invalid','ZZ_HELP_KEY':'k'}),patch.object(h,'save_observations') as save:
    report=h.pull(folder,self.state,self.now,fetch=lambda:data)
   self.assertEqual(report['imported'],2);save.assert_called_once()
   self.assertTrue(json.loads(Path(folder,'help-status.json').read_bytes())['imported']==2)
  parent_b='https://jkanime.net/tokyo-revengers-santen-sensou-hen/';parent_c='https://jkanime.net/steel-ball-run-jojo-no-kimyou-na-bouken/'
  self.assertEqual(self.state['listings'][parent_b]['observedAt'],before['listings'][parent_b]['observedAt'])
  self.assertTrue(self.state['listings'][parent_c]['helpListing']);self.assertEqual(self.state['listings'][parent_c]['episodes'],[c])
  self.assertEqual(self.state['newsSeen'][b],before['newsSeen'][b]);self.assertEqual(self.state['episodes'][a],before['episodes'][a])
  # Imported options pass through the normal build once the app validator approves them.
  link=self.state['episodes'][b]['providers'][0]['links'][0];approved={run.sha(('Mega\0'+link).encode()):True,**fixture(self.now)[1]}
  index,_=run.build(self.state,approved,self.now);self.assertEqual(sum(x['episodes'] for x in index['series'].values()),3)
 def test_key_derives_from_collector_secret(self):
  import hmac,hashlib
  self.assertEqual(h.derived('help-key','s'),hmac.new(b's',b'zzanime-ayuda/help-key',hashlib.sha256).hexdigest());self.assertEqual(h.derived('help-key',''),'')
  self.assertNotEqual(h.derived('help-key','s'),h.derived('salt','s'))
 def test_disabled_or_nothing_asked_makes_no_request(self):
  with tempfile.TemporaryDirectory() as folder:
   def fail():raise AssertionError('no request expected')
   with patch.dict('os.environ',{},clear=True):self.assertEqual(h.pull(Path(folder),self.state,self.now,fetch=fail)['state'],'disabled')
   with patch.dict('os.environ',{'ZZ_HELP_URL':'https://help.invalid','ZZ_HELP_KEY':'k'}):self.assertEqual(h.pull(Path(folder),self.state,self.now,fetch=fail)['state'],'nothing-asked')

class RunIntegrationTests(unittest.TestCase):
 def run_news_only(self,imported,error=None):
  # Empty collector answer; only the help chain may bring something new.
  import os
  result={'passed':True,'primary':'unavailable','errors':{},'diagnostics':{},'recent':[],'state':{'episodes':{},'listings':{},'pending':[]}}
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,*args):return json.dumps(result).encode()
  class Built(Exception):pass
  pull=patch.object(h,'pull',side_effect=error) if error else patch.object(h,'pull',return_value={'imported':imported})
  with tempfile.TemporaryDirectory() as d,pull as puller,patch.object(run,'D',Path(d)),patch.object(run,'load_observations',return_value={'episodes':{},'listings':{},'newsSeen':{},'pending':[]}),patch.object(run,'save_observations'),patch.object(run,'compile_java',side_effect=Built),patch('urllib.request.urlopen',return_value=Response()),patch.dict(os.environ,{'ZZ_COLLECTOR_URL':'https://collector.invalid','ZZ_COLLECTOR_KEY':'test-only','ZZ_HELP_URL':'https://help.invalid','ZZ_HELP_KEY':'k'}),patch('sys.argv',['run.py','--news-only','--collect','--publish']),patch('link_health.check',return_value={'excluded':0}):
   try:run.main();built=False
   except Built:built=True
   puller.assert_called_once()
  return built
 def test_help_import_triggers_publication(self):
  self.assertFalse(self.run_news_only(0));self.assertTrue(self.run_news_only(1))
 def test_failing_help_service_never_blocks(self):
  self.assertFalse(self.run_news_only(0,error=OSError('help down')))

class LegacyReaderTests(unittest.TestCase):
 def test_installed_readers_accept_signed_channel_with_wanted(self):
  now=datetime.datetime.now(datetime.timezone.utc);state,approved,urls=fixture(now);key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);public=root/'key.der';public.write_bytes(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))
   index,files=run.build(state,approved,now);body=run.raw(index);digest=run.sha(body);path='indexes/'+digest+'.bin';files[path]=body;results=[]
   wanted=h.wanted(state,files,now,{'mode':'open','trial':TRIAL,'max':40},{})
   cp=run.compile_java(root/'old')
   for extra in [{},{'wanted':wanted}]:
    payload=run.raw({'schema':1,'sequence':int(now.timestamp()*1000),'createdAt':iso(now),'indexSha256':digest,'indexPath':path,'indexBytes':len(body),'mode':'daily-new',**extra})
    site=root/('site'+str(len(results)))
    for n,b in {**files,'channel.json':run.raw({'payload':payload.decode(),'signature':key.sign(payload,padding.PKCS1v15(),hashes.SHA256()).hex()})}.items():run.put(site/n,b)
    results.append(json.loads(run.command(['java','-cp',cp,'tv.jkanime.web.CloudVerify',str(site),str(public),str(root/('cache'+str(len(results))))])))
   self.assertEqual(len(wanted),2);self.assertEqual(results[0],results[1])

if __name__=='__main__':unittest.main()
