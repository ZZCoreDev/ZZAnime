"""14/11/2026 (Robin): «Publicar app» from the editor. Run by .github/workflows/publish-app.yml.

Takes the APK the owner uploaded in the editor (by its random id), and publishes it in release v1.0 exactly like
work/cloud-integration/release_mobile.py / release_tv.py do on the PC: same checks (official signature only, package,
versionName 1.1, higher versionCode, no sensor/local-network permission, the current APK matches its manifest) and the
same stage -> verify -> rename -> verify sequence. Before replacing, the current APK and manifest are kept in the
prerelease «anteriores» (last 3 per kind) so it can be put back. Nothing is published if any check fails.
Inputs come from the environment (never pasted into the shell): KIND, UPLOAD, SHA256, NOTES."""
import hashlib,json,os,re,shutil,subprocess,sys,tempfile,urllib.request
from pathlib import Path
REPO=os.environ.get('GITHUB_REPOSITORY','ZZCoreDev/ZZAnime');TAG='v1.0';BACKUP='anteriores';KEEP=3
OFFICIAL='71eabff504d6da93e1ab47ff83b6cc38bb002cdad6bc8a0ab93bc6fbbe40fd72';MAX=24*1024*1024
KINDS={'mobile':{'package':'tv.jkanime.mobile','names':['ZZAnimeMobile.apk','JKAnimeMobile.apk'],'manifest':'update-mobile.json','label':'Móvil'},
       'tv':{'package':'tv.jkanime.web','names':['ZZAnimeTV.apk','JKAnimeTV.apk'],'manifest':'update.json','label':'TV'}}
FORBIDDEN=['android.permission.OTHER_SENSORS','android.permission.ACCESS_LOCAL_NETWORK']
def fail(msg):
    print('NO PUBLICADA: '+msg);summary('### No publicada\n\n'+msg);sys.exit(1)
def summary(text):
    p=os.environ.get('GITHUB_STEP_SUMMARY')
    if p:
        with open(p,'a',encoding='utf-8') as f:f.write(text+'\n')
def run(*a,**k):return subprocess.run([str(x) for x in a],check=True,capture_output=True,text=True,**k).stdout
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def api(path,*a):return json.loads(run('gh','api',path,*a))
def inputs(env):
    kind,upload,digest,notes=env.get('KIND',''),env.get('UPLOAD',''),env.get('SHA256',''),env.get('NOTES','')
    if kind not in KINDS:fail('tipo de app desconocido')
    if not re.fullmatch(r'[0-9a-f]{32}',upload):fail('identificador de subida no válido')
    if not re.fullmatch(r'[0-9a-f]{64}',digest):fail('huella no válida')
    if not 3<=len(notes)<=300 or re.search(r'[\x00-\x1f\x7f-\x9f\u2028\u2029]',notes):fail('notas no válidas')
    return kind,upload,digest,notes
def certificates(apksigner_output):
    """Every certificate digest apksigner prints (a signer whose name contains the official text adds another value)."""
    return sorted(set(re.findall(r'certificate SHA-256 digest: ([0-9a-f]{64})',apksigner_output)))
def badging(line):
    m=re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']*)'",line)
    if not m:fail('no se pudo leer el paquete de la APK')
    return m[1],int(m[2]),m[3]
def check_apk(apk,kind,previous_code,bt):
    out=subprocess.run([str(bt/'apksigner'),'verify','--print-certs',str(apk)],capture_output=True,text=True)
    if out.returncode!=0:fail('la firma de la APK no es válida')
    if certificates(out.stdout+out.stderr)!=[OFFICIAL]:fail('la APK no está firmada con la llave oficial de ZZAnime')
    perms=run(bt/'aapt2','dump','permissions',apk)
    if any(p in perms for p in FORBIDDEN):fail('la APK pide un permiso no permitido (sensores o red local)')
    package,code,name=badging(run(bt/'aapt2','dump','badging',apk).splitlines()[0])
    if package!=KINDS[kind]['package']:fail('la APK es de otro tipo ('+package+'); elegiste '+KINDS[kind]['label'])
    if name!='1.1':fail('versionName inesperado: '+name)
    if code<=previous_code:fail(f'la versión {code} no es mayor que la publicada ({previous_code})')
    return code
def keep_previous(kind,code,files):
    """Current APK + manifest into the prerelease «anteriores»; only the last KEEP versions per kind stay."""
    try:api('repos/'+REPO+'/releases/tags/'+BACKUP)
    except subprocess.CalledProcessError:run('gh','release','create',BACKUP,'--repo',REPO,'--prerelease','--title','Versiones anteriores de la app','--notes','Copias para volver atrás. Las crea «Publicar app» antes de reemplazar una versión.')
    run('gh','release','upload',BACKUP,'--repo',REPO,'--clobber',*files)
    assets=api('repos/'+REPO+'/releases/tags/'+BACKUP)['assets'];prefix=kind+'-'
    versions=sorted({int(m[1]) for a in assets if (m:=re.match(re.escape(prefix)+r'(\d+)\.',a['name']))},reverse=True)
    for a in assets:
        m=re.match(re.escape(prefix)+r'(\d+)\.',a['name'])
        if m and int(m[1]) not in versions[:KEEP]:run('gh','api','--method','DELETE','repos/'+REPO+'/releases/assets/'+str(a['id']))
def main():
    kind,upload,digest,notes=inputs(os.environ);k=KINDS[kind];names=k['names']+[k['manifest']]
    bt=sorted(Path(os.environ['ANDROID_HOME'],'build-tools').iterdir(),key=lambda p:[int(x) if x.isdigit() else 0 for x in re.split(r'[.-]',p.name)])[-1]
    work=Path(tempfile.mkdtemp(prefix='app-'));apk=work/'upload.apk'
    req=urllib.request.Request('https://editor.zzanime.uk/api/app-upload/'+upload+'.apk',headers={'User-Agent':'ZZAnime-PublishApp/1'})
    try:
        with urllib.request.urlopen(req,timeout=120) as r:data=r.read(MAX+1)
    except Exception:fail('no se pudo descargar la APK subida (¿caducó? se guarda 2 horas)')
    if len(data)>MAX:fail('APK demasiado grande')
    apk.write_bytes(data)
    if sha(apk)!=digest:fail('la APK descargada no es la que se subió (huella distinta)')
    release=api('repos/'+REPO+'/releases/tags/'+TAG);old={x['name']:x for x in release['assets']}
    before=work/'before';before.mkdir()
    for name in names:run('gh','release','download',TAG,'--repo',REPO,'--dir',before,'--pattern',name)
    previous=json.loads((before/k['manifest']).read_text(encoding='utf-8'))
    # repaso 14/11: BOTH published copies (ZZAnime… and JKAnime…) must match the manifest; the ZZAnime one is what is kept
    if any(sha(before/n)!=previous['sha256'] for n in k['names']):fail('la versión publicada no coincide con su manifiesto; no se toca nada')
    code=check_apk(apk,kind,previous['versionCode'],bt)
    # copy of what is published now, to put it back if needed
    label=kind;keep=work/'keep';keep.mkdir()
    shutil.copy2(before/names[0],keep/f"{label}-{previous['versionCode']}.apk");shutil.copy2(before/k['manifest'],keep/f"{label}-{previous['versionCode']}.json")
    keep_previous(kind,previous['versionCode'],sorted(keep.iterdir()))
    out=work/'new';out.mkdir()
    for name in k['names']:shutil.copy2(apk,out/name)
    previous.update(versionCode=code,sha256=sha(apk),bytes=apk.stat().st_size,notes=notes);previous.pop('rollout',None)
    (out/k['manifest']).write_text(json.dumps(previous,ensure_ascii=False,indent=2),encoding='utf-8')
    staging=work/'staging';staging.mkdir()
    for name in names:shutil.copy2(out/name,staging/(name+'.pending'))
    if {x['name']:x['id'] for x in api('repos/'+REPO+'/releases/tags/'+TAG)['assets']}!={x['name']:x['id'] for x in release['assets']}:fail('la publicación cambió mientras tanto; prueba otra vez')
    run('gh','release','upload',TAG,'--repo',REPO,'--clobber',*[staging/(n+'.pending') for n in names])
    by_name={x['name']:x for x in api('repos/'+REPO+'/releases/tags/'+TAG)['assets']}
    checked=work/'staged-verify';checked.mkdir()
    for name in names:run('gh','release','download',TAG,'--repo',REPO,'--dir',checked,'--clobber','--pattern',name+'.pending')
    for name in names:
        if by_name[name+'.pending']['size']!=(out/name).stat().st_size or sha(checked/(name+'.pending'))!=sha(out/name):fail('copia de prueba distinta: '+name)
    for name in names:
        if name in old:run('gh','api','--method','DELETE','repos/'+REPO+'/releases/assets/'+str(old[name]['id']))
        body=work/'rename.json';body.write_text(json.dumps({'name':name}),encoding='utf-8')
        run('gh','api','--method','PATCH','repos/'+REPO+'/releases/assets/'+str(by_name[name+'.pending']['id']),'--input',body)
    verify=work/'published';verify.mkdir()
    for name in names:run('gh','release','download',TAG,'--repo',REPO,'--dir',verify,'--clobber','--pattern',name)
    for name in names:
        if sha(verify/name)!=sha(out/name):fail('lo publicado no coincide: '+name)
    print(json.dumps({'published':names,'kind':kind,'versionCode':code,'previous':previous_code_text(before,k),'sha256':digest}))
    summary(f"### Publicada {k['label']} {code}\n\n{notes}\n\nLa anterior queda guardada en la publicación «{BACKUP}».")
def previous_code_text(before,k):return json.loads((before/k['manifest']).read_text(encoding='utf-8'))['versionCode']
if __name__=='__main__':main()
