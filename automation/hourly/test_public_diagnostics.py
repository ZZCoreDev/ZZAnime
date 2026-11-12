"""R6-07: the two-series proof failure (public Actions log) never carries collector messages or addresses."""
import json,sys,types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import run
errors={'https://jkanime.net/psyren/1/':'SyntaxError: Unexpected token \'h\', "https://x.invalid/xx" is not valid JSON','https://jkanime.net/other/3/':'x'}
diag={'https://jkanime.net/psyren/1/':{'jk':{'stage':'detail','status':200,'cause':'parser-or-network','message':'"https://x.invalid/xx" is not valid JSON','retryAt':'2026-11-12T10:00:00Z'},'tio':{'stage':'https://x.invalid','status':'200','cause':'https://evil.invalid/','cachedFailure':True},'evil':{'stage':'x'}},
      'https://jkanime.net/dark-summoner-to-dekiteiru/1/':{'flv':{'stage':'complete','status':200,'cause':'observed-options'}}}
out=run.public_diagnostics(errors,diag,lambda k:'psyren' in k or 'dark-summoner' in k)
text=json.dumps(out)
assert 'invalid' not in text and 'http' not in text and 'message' not in text and 'Unexpected' not in text,text
assert set(out)=={'psyren/1','dark-summoner-to-dekiteiru/1'},out
assert out['psyren/1']=={'failed':True,'jk':{'stage':'detail','status':200,'cause':'parser-or-network','retryAt':'2026-11-12T10:00:00Z'},'tio':{'stage':'other','status':None,'cause':'other','cachedFailure':True}},out
assert out['dark-summoner-to-dekiteiru/1']=={'failed':False,'flv':{'stage':'complete','status':200,'cause':'observed-options'}}
assert run.public_diagnostics(None,None,lambda k:True)=={}
src=Path(run.__file__).read_text(encoding='utf-8')
assert "json.dumps(v)[:300]" not in src and "str(v)[:160]" not in src
print('R6-07 public proof diagnostics PASS')
