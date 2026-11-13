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
