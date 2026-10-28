"""Explicit public code bundle only. Does not enable cron, create credentials or deploy GPU."""
from pathlib import Path
import base64,hashlib,json,re,subprocess,sys
HERE=Path(__file__).resolve().parents[1];R=HERE.parents[1];OUT=R/'work/dubbing-validation';sys.path.insert(0,str(R/'work/backup-delivery'))
from install_cloud import api,tree_commit
def main()->None:
 proof=json.loads((OUT/'verification.json').read_text(encoding='utf-8'));qa=json.loads((OUT/'proof.json').read_text(encoding='utf-8'))
 if not proof['passed'] or not qa['qa_passed'] or not qa['source_transcription_complete']:raise ValueError('Real local proof required before installation')
 repository=json.loads(subprocess.check_output(['gh','api','repos/ZZCoreDev/ZZAnime'],text=True,encoding='utf-8'))
 if repository['private']:raise ValueError('This bundle is restricted to the existing public/free Actions repository')
 files={}
 for path in sorted(HERE.rglob('*')):
  if not path.is_file() or '__pycache__' in path.parts:continue
  rel=path.relative_to(HERE)
  if path.suffix not in {'.py','.yml','.yaml','.txt','.md'} and path.name not in {'Dockerfile','.gitignore','.dockerignore'} and str(rel).replace('\\','/') not in {'state/processed.json','tools/lifecycle.json'}:continue
  raw=path.read_bytes()
  if len(raw)>200000 or re.search(rb'(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s*$',raw) or path.name.startswith('.env'):raise ValueError('Private/large file forbidden')
  files['automation/dubbing/'+rel.as_posix()]=raw
 workflow='.github/workflows/pipeline.yml';body=(R/workflow).read_bytes()
 try:existing=base64.b64decode(api('contents/'+workflow+'?ref=main')['content'])
 except RuntimeError as error:
  if '404' not in str(error):raise
  existing=None
 if existing and b'name: Doblaje autorizado' not in existing:raise ValueError('Existing unrelated workflow preserved; choose another filename')
 files[workflow]=body;subprocess.run(['gh','variable','set','ZZ_DUBBING_ENABLED','--repo','ZZCoreDev/ZZAnime','--body','false'],check=True,capture_output=True);head=tree_commit('main',files,'Añadir prueba local de doblaje autorizado; GPU y publicación desactivadas')
 subprocess.run(['gh','workflow','run','pipeline.yml','--repo','ZZCoreDev/ZZAnime','--ref','main','-f','dry_run=true'],check=True,capture_output=True);receipt={'commit':head,'files':{p:hashlib.sha256(b).hexdigest() for p,b in files.items()},'cron_enabled':False,'gpu_deployed':False,'dry_run_dispatched':True,'private_keys_uploaded':False};(OUT/'code-installation.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print('Public code installed; CPU-only CI dispatched; cron/GPU/uploads remain disabled')
if __name__=='__main__':main()
