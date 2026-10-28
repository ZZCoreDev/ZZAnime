import copy,datetime,gzip,json,os,tempfile,unittest
from pathlib import Path
from archive_state import load,save,merge,stamp
from renew import select,validate,status_document,DAY

class RenewalTests(unittest.TestCase):
    def fixture(self,age=2):
        now=datetime.datetime.now(datetime.timezone.utc);parent='https://jkanime.net/psyren/';url=parent+'4/';observed=(now-datetime.timedelta(days=age)).isoformat()
        return now,parent,url,{'schema':1,'episodes':{url:{'complete':True,'observedAt':observed,'providers':[{'family':'mp4upload','name':'Mp4upload','links':['https://www.mp4upload.com/embed-test.html']}]}},'listings':{parent:{'complete':True,'observedAt':observed,'episodes':[parent+str(n)+'/' for n in range(1,5)]}},'pending':[]}
    def temporary(self):
        path=Path(__file__).parent/'test-runtime';path.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=path)
    def test_select_before_seven_days(self):
        now,_,url,state=self.fixture(2);self.assertEqual(select(state,{},now.timestamp(),2),[url])
    def test_fresh_not_repeated(self):
        now,_,_,state=self.fixture(0);self.assertEqual(select(state,{},now.timestamp(),2),[])
    def test_failure_backoff(self):
        now,_,url,state=self.fixture();self.assertEqual(select(state,{url:{'retryAt':now.timestamp()+900}},now.timestamp(),2),[])
    def test_old_observation_cannot_be_renewed_by_timestamp_only(self):
        now,_,url,state=self.fixture()
        with self.assertRaises(ValueError):validate(state,[url],now.timestamp(),now.timestamp())
    def test_fresh_observation_requires_observed_identity(self):
        now,parent,url,state=self.fixture(0);validate(state,[url],now.timestamp(),now.timestamp())
        state['listings'][parent]['episodes']=[]
        with self.assertRaises(ValueError):validate(state,[url],now.timestamp(),now.timestamp())
    def test_no_unrequested_episode(self):
        now,_,_,state=self.fixture(0)
        with self.assertRaises(ValueError):validate(state,[],now.timestamp(),now.timestamp())
    def test_sharded_roundtrip_keeps_dates_and_listed_chapters(self):
        _,parent,url,state=self.fixture();original=copy.deepcopy(state)
        with self.temporary() as path:
            save(path,state);loaded=load(path);self.assertEqual(loaded,state)
            file=next((Path(path)/'series-state').glob('*.gz'));first=file.read_bytes();save(path,loaded);self.assertEqual(file.read_bytes(),first)
            self.assertEqual(len(loaded['listings'][parent]['episodes']),4);self.assertEqual(loaded['episodes'][url]['observedAt'],original['episodes'][url]['observedAt'])
    def test_newest_wins_and_old_chapters_not_lost(self):
        _,parent,url,old=self.fixture(2);_,_,_,fresh=self.fixture(0)
        fresh['listings'][parent]['episodes']=[url];merge(old,fresh);merge(old,self.fixture(3)[3]);self.assertEqual(old['episodes'][url]['observedAt'],fresh['episodes'][url]['observedAt']);self.assertEqual(len(old['listings'][parent]['episodes']),4)
    def test_failure_report_is_idempotent_and_keeps_manual_notes(self):
        with self.temporary() as temp:
            p=Path(temp)/'ESTADO.md';p.write_text('Notas manuales\n');s={'state':'failed','failed':2,'expired':1};status_document(p,s);first=p.read_bytes();status_document(p,s);self.assertEqual(first,p.read_bytes());self.assertIn('Deuda:',p.read_text());self.assertTrue(p.read_text().startswith('Notas manuales'))
    def test_corrupt_shard_rejected(self):
        _,_,_,state=self.fixture()
        with self.temporary() as temp:
            save(temp,state);p=next((Path(temp)/'series-state').glob('*.gz'));row=json.loads(gzip.decompress(p.read_bytes()));row['series']='https://jkanime.net/other/';p.write_bytes(gzip.compress(json.dumps(row).encode()))
            with self.assertRaises(ValueError):load(temp)

if __name__=='__main__':unittest.main()
