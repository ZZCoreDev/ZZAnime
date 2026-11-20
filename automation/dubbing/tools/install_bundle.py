"""Explicit public code bundle only. Does not enable cron, create credentials or deploy GPU."""
from pathlib import Path
import base64,hashlib,json,os,re,stat,subprocess,sys
HERE=Path(__file__).resolve().parents[1];R=HERE.parents[1];OUT=R/'work/dubbing-validation';sys.path.insert(0,str(R/'work/backup-delivery'))
def local_bundle_file(root: Path, candidate: Path) -> Path:
 resolved_root = root.resolve(strict=True)
 absolute = Path(os.path.abspath(candidate))
 if candidate.is_symlink() or not absolute.is_relative_to(resolved_root):
  raise ValueError('Bundle file must be a regular file within the source tree')
 resolved = candidate.resolve(strict=True)
 # Resolution must be the identity: no symlink may appear in the file or any parent component.
 if resolved != absolute or not resolved.is_relative_to(resolved_root) or not stat.S_ISREG(os.lstat(resolved).st_mode):
  raise ValueError('Bundle file must be a regular file within the source tree')
 return resolved

def read_bundle_bytes(root: Path, candidate: Path) -> bytes:
 resolved = local_bundle_file(root, candidate)
 # O_NOFOLLOW closes the check-to-read window: a link swapped in after validation is refused, not dereferenced.
 fd = os.open(resolved, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0))
 with os.fdopen(fd, 'rb') as handle:
  if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
   raise ValueError('Bundle file must be a regular file within the source tree')
  return handle.read()

def main()->None:
 from install_cloud import api,tree_commit
 proof=json.loads((OUT/'verification.json').read_text(encoding='utf-8'));qa=json.loads((OUT/'proof.json').read_text(encoding='utf-8'))
 if not proof['passed'] or not qa['qa_passed'] or not qa['source_transcription_complete']:raise ValueError('Real local proof required before installation')
 repository=json.loads(subprocess.check_output(['gh','api','repos/ZZCoreDev/ZZAnime'],text=True,encoding='utf-8'))
 if repository['private']:raise ValueError('This bundle is restricted to the existing public/free Actions repository')
 files={}
 for path in sorted(HERE.rglob('*')):
  if path.is_symlink():raise ValueError('Symbolic links are forbidden in the public bundle: '+str(path.relative_to(HERE)))
  if '__pycache__' in path.parts:continue
  if not path.is_file():continue
  rel=path.relative_to(HERE)
  if path.suffix not in {'.py','.yml','.yaml','.txt','.md'} and path.name not in {'Dockerfile','.gitignore','.dockerignore'} and str(rel).replace('\\','/') not in {'state/processed.json','tools/lifecycle.json'}:continue
  raw=read_bundle_bytes(HERE,path)
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
