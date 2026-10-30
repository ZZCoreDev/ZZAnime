"""AnimeFLV now offers only Mega + Voe for new episodes; an approved Mega option must reach the root channel."""
import datetime,unittest
import run
MEGA='https://mega.nz/embed/1bMBVLLA#gMsRZdTOEXkHrxfgIJZlNcYVawn2m5BcXFtNvBgP0fQ'
class FlvMegaBuild(unittest.TestCase):
 def test_flv_mega_option_is_published(self):
  now=datetime.datetime.now(datetime.timezone.utc);seen=(now-datetime.timedelta(hours=1)).isoformat().replace('+00:00','Z')
  url='https://jkanime.net/tokyo-revengers-santen-sensou-hen/5/';parent=url.rsplit('/',2)[0]+'/'
  state={'episodes':{url:{'observedAt':seen,'complete':True,'sourceSeries':'https://vww.animeflv.one/anime/tokyo-revengers-santen-sensou-hen','providers':[{'family':'mega','name':'Mega','links':[MEGA]},{'family':'voe','name':'Voe','links':['https://voe.sx/e/abcdefgh1234']}]}},
         'listings':{parent:{'observedAt':seen,'episodes':[url]}},'newsSeen':{url:seen}}
  approved={run.sha(('Mega'+chr(0)+''+MEGA).encode()):True,run.sha(('Voe'+chr(0)+'https://voe.sx/e/abcdefgh1234').encode()):True}
  index,files=run.build(state,approved,now)
  self.assertEqual([e['url'] for e in index['feed']['episodes']],[url])
  import gzip,json;row=json.loads(gzip.decompress(files[index['series'][run.sha(parent.encode())]['path']]))
  self.assertEqual([o['family'] for o in row['episodes'][0]['options']],['mega'],'Mega kept, VOE left to its complement')
if __name__=='__main__':unittest.main()
