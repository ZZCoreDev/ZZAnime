import copy,tempfile,unittest,urllib.error
from pathlib import Path
import collect
def media(identity=114):return {'id':identity,'format':'TV_SHORT','seasonYear':2003,'title':{'romaji':'Example'},'synonyms':[],'coverImage':{'extraLarge':f'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx{identity}-example.jpg'},'studios':{'nodes':[{'name':'Example'}]}}
class CloudTests(unittest.TestCase):
 def test_schema(self):collect.validate(media(),{114})
 def test_foreign_identity(self):
  with self.assertRaises(ValueError):collect.validate(media(383),{114})
 def test_foreign_cover(self):
  m=media();m['coverImage']['extraLarge']=media(383)['coverImage']['extraLarge']
  with self.assertRaises(ValueError):collect.validate(m,{114})
 def test_proof_two_then_cached(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
   seed={'ids':[114,383],'proofIds':[114,383]};calls=[]
   def get(ids):calls.append(ids);return [media(i) for i in ids]
   first=collect.run(Path(tmp),seed,True,get,lambda:1000000,lambda _:None);second=collect.run(Path(tmp),seed,False,get,lambda:1000100,lambda _:None)
   self.assertEqual(first['fetched'],2);self.assertEqual(second['fetched'],0);self.assertEqual(len(calls),1)
 def test_failure_retains_checkpoint(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
   seed={'ids':[114,383],'proofIds':[114,383]};folder=Path(tmp);collect.run(folder,seed,True,lambda ids:[media(i) for i in ids],lambda:1000000,lambda _:None);previous=(folder/'metadata.json.gz').read_bytes()
   def fail(ids):raise urllib.error.HTTPError('https://graphql.anilist.co',429,'paused',{'Retry-After':'90000'},None)
   with self.assertRaises(urllib.error.HTTPError):collect.run(folder,seed,True,fail,lambda:2000000,lambda _:None)
   self.assertEqual(previous,(folder/'metadata.json.gz').read_bytes());self.assertTrue((folder/'ESTADO.md').exists())
if __name__=='__main__':unittest.main()
