"""C2: aliases approved only with equal year, chapter count and season/variant marks; the rest to review."""
import json,unittest
from pathlib import Path
import identity_filter as f
W=Path(__file__).resolve().parent
CAT={'https://jkanime.net/maid-s/':{'url':'https://jkanime.net/maid-s/','title':'Kobayashi-san Chi no Maid Dragon S','year':2021},
     'https://jkanime.net/keroro-gunsou-2026/':{'url':'https://jkanime.net/keroro-gunsou-2026/','title':'Keroro Gunsou☆ 2026','year':2026},
     'https://jkanime.net/show-2nd-season/':{'url':'https://jkanime.net/show-2nd-season/','title':'Show 2nd Season','year':2020}}
def row(line):return f.parse(line)
class IdentityFilterTests(unittest.TestCase):
    def test_keroro_is_approved_and_becomes_an_entry_without_collector(self):
        r=row('keroro-gunsou-2026\t2026\t4\ttio=keroro-gunsou|Keroro Gunsou☆|4\tflv=keroro-gunsou|Keroro Gunsou☆|4')
        self.assertEqual(f.review(r,CAT,{},4),[]);e=f.entry(r,CAT)
        self.assertEqual(e['title'],'Keroro Gunsou☆ 2026');self.assertNotIn('collector',e);self.assertEqual(e['sources']['flv']['slug'],'keroro-gunsou')
    def test_each_rule_sends_to_review(self):
        base='show-2nd-season\t2020\t12\ttio=show-2|Show 2|12'
        self.assertEqual(f.review(row(base),CAT,{},12),[])
        cases={'show-2nd-season\t2019\t12\ttio=show-2|Show 2|12':'year','show-2nd-season\t2020\t12\ttio=show-2|Show 2|11':'tio-chapters',
               'show-2nd-season\t2020\t12\ttio=show|Show|12':'tio-marks','show-2nd-season\t2020\t12\ttio=show-2-latino|Show 2 Latino|12':'tio-dub',
               'show-2nd-season\t2020\t12\ttio=show-movie-2|Show 2 Movie|12':'tio-marks','show-2nd-season\t2020\t12\ttio=show-2|Show 2|12\tflv=show-ii|Show II|12':'flv-not-tio-slug','show-2nd-season\t2020\t12\tflv=show-2|Show 2|12':'no-tio'}
        for line,reason in cases.items():self.assertIn(reason,f.review(row(line),CAT,{},12),line)
        self.assertIn('jk-listing',f.review(row(base),CAT,{},11));self.assertIn('jk-listing',f.review(row(base),CAT,{},None))
        self.assertEqual(f.review(row('unknown\t2020\t1\ttio=x|X|1'),CAT,{},1),['not-in-catalogue'])
        taken={'https://jkanime.net/other/':{'sources':{'tio':{'slug':'show-2','title':'Show 2'}}}}
        self.assertIn('tio-slug-taken',f.review(row(base),CAT,taken,12))
        self.assertIn('already-mapped',f.review(row(base),CAT,{'https://jkanime.net/show-2nd-season/':{}},12))
    def test_marks_follow_filter_py(self):
        self.assertEqual(f.marks('Kobayashi-san Chi no Maid Dragon S'),{'s2'});self.assertEqual(f.marks('Fate/kaleid liner Prisma☆Illya 3rei!! Special'),{'s3','extra'})
        self.assertEqual(f.marks('Code Geass: Hangyaku no Lelouch R2'),f.marks('Code Geass: R2'));self.assertEqual(f.marks('Kyoukai Senjou no Horizon II'),f.marks('kyoukai senjou no horizon ii'))
        self.assertEqual(f.toks('Märchen Mädchen ½'),['marchen','madchen','12'])
        self.assertEqual(f.decode('JoJo&amp;#039;s'),"JoJo's")
    def test_every_approved_entry_in_the_repo_keeps_these_rules(self):
        cat={r['url']:r for r in json.loads((W/'catalogue.json').read_bytes())};ids=json.loads((W/'source-identities.json').read_bytes())
        for url,e in ids.items():
            if not e.get('approved'):continue
            jk=f.marks(cat[url]['title'],url.split('/')[3].replace('-',' '))
            for name,s in e['sources'].items():
                self.assertEqual(f.marks(s['title'],s['slug'].replace('-',' ')),jk,(url,name))
                self.assertFalse(f.DUB&set(f.toks(s['title'])+f.toks(s['slug'])),(url,name))
                self.assertEqual([o for o,x in ids.items() if x.get('sources',{}).get(name,{}).get('slug')==s['slug']],[url],(url,name))
            # Mao and Mezametara predate C2 (manual, no 'episodes'): FLV there uses its own slug.
            if 'episodes' in e and 'flv' in e['sources']:self.assertEqual(e['sources']['flv']['slug'],e['sources']['tio']['slug'],url)
if __name__=='__main__':unittest.main()
