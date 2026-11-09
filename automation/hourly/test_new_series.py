import tempfile,unittest
from pathlib import Path
import new_series
TIO='<title>Demons&#039; Crest - TioAnime</title>';FLV='<title>Ver Demons\' Crest Online \u2714 AnimeFLV</title>'
def fake(pages):
    return lambda url:(200,url,pages[url]) if url in pages else (404,url,'')
class NewSeriesTests(unittest.TestCase):
    def run_verify(self,pages,slugs,catalogue=()):
        d=tempfile.mkdtemp();new_series.verify(d,slugs,list(catalogue),now=1000,fetcher=fake(pages),sleep=lambda s:None);return d
    def test_same_slug_and_title_on_both_sources_is_accepted(self):
        d=self.run_verify({'https://tioanime.com/anime/demons-crest':TIO,'https://vww.animeflv.one/anime/demons-crest':FLV},['demons-crest'])
        self.assertEqual(new_series.rows(d),[{'url':'https://jkanime.net/demons-crest/','title':"Demons' Crest",'year':None}])
    def test_missing_source_or_other_title_is_rejected_and_waits(self):
        d=self.run_verify({'https://tioanime.com/anime/x-y':TIO,'https://vww.animeflv.one/anime/x-y':'<title>Ver Otra Online \u2714 AnimeFLV</title>','https://tioanime.com/anime/solo':TIO},['x-y','solo'])
        data=new_series.load(d);self.assertEqual(new_series.rows(d),[]);self.assertEqual(data['rejected']['https://jkanime.net/x-y/']['reason'],'titles differ');self.assertEqual(data['rejected']['https://jkanime.net/solo/']['retryAt'],1000+7*86400)
    def test_catalogue_title_under_other_slug_is_not_duplicated(self):
        d=self.run_verify({'https://tioanime.com/anime/demons-crest':TIO,'https://vww.animeflv.one/anime/demons-crest':FLV},['demons-crest'],[{'url':'https://jkanime.net/demons-crest-tv/','title':"Demons' Crest"}])
        self.assertEqual(new_series.rows(d),[]);self.assertEqual(new_series.load(d)['rejected']['https://jkanime.net/demons-crest/']['reason'],'title already in catalogue')
    def test_bounded_and_catalogue_slugs_skipped(self):
        calls=[];d=tempfile.mkdtemp()
        n=new_series.verify(d,['a1','a2','a3','a4','known'],[{'url':'https://jkanime.net/known/','title':'K'}],now=1,fetcher=lambda u:(calls.append(u),(404,u,''))[1],sleep=lambda s:None)
        self.assertEqual(n,3);self.assertEqual(len(calls),6)
if __name__=='__main__':unittest.main()
