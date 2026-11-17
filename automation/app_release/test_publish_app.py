"""14/11/2026: checks of «Publicar app» that run before anything is published (inputs, signature list, package line)."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import publish_app as p
def refused(fn,*a):
    try:fn(*a)
    except SystemExit:return True
    return False
ok={'KIND':'mobile','UPLOAD':'0123456789abcdef0123456789abcdef','SHA256':'a'*64,'NOTES':'Arreglos del reproductor.'}
assert p.inputs(ok)==('mobile',ok['UPLOAD'],'a'*64,'Arreglos del reproductor.')
for bad in [{'KIND':'pc'},{'KIND':''},{'UPLOAD':'../../x'},{'UPLOAD':'0123'},{'SHA256':'z'*64},{'NOTES':'no'},{'NOTES':'x'*301},{'NOTES':'a\nb'},{'NOTES':'a\u2028b'}]:
    assert refused(p.inputs,{**ok,**bad}),bad
off='71eabff504d6da93e1ab47ff83b6cc38bb002cdad6bc8a0ab93bc6fbbe40fd72'
assert p.certificates('Signer #1 certificate SHA-256 digest: '+off+'\n')==[off]
two='Signer #1 certificate SHA-256 digest: '+off+'\nSigner #2 certificate SHA-256 digest: '+'b'*64+'\n'
assert p.certificates(two)!=[off],'a second signer is refused'
assert p.certificates('Signer #1 certificate DN: CN='+off+'\n')==[],'an official-looking name is not a digest'
assert p.badging("package: name='tv.jkanime.mobile' versionCode='199' versionName='1.1' platformBuildVersionName='15'")==('tv.jkanime.mobile',199,'1.1')
assert refused(p.badging,'garbage')
print('publicar app: entradas, firmas y paquete OK')
# R11-07 (18/11): a rename that keeps failing after the old copy was removed puts the previous version back.
import time as _t,tempfile as _tf
_t.sleep=lambda s:None
state={'a.apk':1,'a.apk.pending':2,'m.json':3,'m.json.pending':4};calls=[]
def fake_api(path,*a):return {'assets':[{'name':n,'id':i} for n,i in state.items()]}
def fake_run(*a):
    calls.append(a)
    if 'DELETE' in a:state.pop([n for n,i in state.items() if str(i)==a[-1].rsplit('/',1)[1]][0])
    elif 'PATCH' in a:raise RuntimeError('red caída')
    elif 'upload' in a:state.update({Path(x).name:9 for x in a if str(x).endswith(('.apk','.json'))})
p.api,p.run=fake_api,fake_run
work=Path(_tf.mkdtemp())
try:p.promote(['a.apk','m.json'],{'a.apk.pending':{'id':2},'m.json.pending':{'id':4}},work);raise AssertionError('debía fallar')
except RuntimeError:pass
assert 'a.apk' not in state  # the failure the review reproduced
p.restore(['a.apk','m.json'],work)
assert 'a.apk' in state and 'm.json' in state
# a lost answer: the new copy already has the final name, nothing is removed again
state.clear();state.update({'a.apk':2});calls.clear();p.promote(['a.apk'],{'a.apk.pending':{'id':2}},work);assert not calls
print('publicar app: cambio recuperable OK')
