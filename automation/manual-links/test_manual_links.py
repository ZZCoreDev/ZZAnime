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
if __name__=='__main__':unittest.main()
