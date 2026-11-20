from __future__ import annotations
import dataclasses,os,shutil,subprocess,sys,time
from pathlib import Path, PureWindowsPath
from . import ingest,separate,transcribe,translate,tts,fit,mix,qa
from .core import Cache,Episode,digest,read,save
def contained_path(root: Path, name: str) -> Path:
 if not isinstance(name, str) or not name:
  raise ValueError('The step must return a relative path')
 relative = Path(name)
 windows = PureWindowsPath(name)
 if relative.anchor or windows.anchor or '..' in relative.parts or '..' in windows.parts or ':' in name:
  raise ValueError('The step returned an invalid relative path')
 resolved_root = root.resolve()
 candidate = (resolved_root / relative).resolve()
 if candidate == resolved_root or not candidate.is_relative_to(resolved_root):
  raise ValueError('The step path is outside its workspace')
 return candidate

def isolated(name:str,out:Path,args:list,timeout:int)->dict:
 request=out/'worker-request.json';save(request,{'step':name,'out':str(out),'args':[str(x) if isinstance(x,Path) else x for x in args]});env=dict(os.environ);env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])+os.pathsep+env.get('PYTHONPATH','')
 process=subprocess.run([sys.executable,'-X','utf8','-m','dubpipe.step_worker',str(request)],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout);(out/'worker.log').write_text(process.stdout+'\n'+process.stderr,encoding='utf-8')
 if process.returncode:raise RuntimeError(name+' failed; inspect '+str(out/'worker.log'))
 return read(out/'worker-result.json')
def execute(episode:Episode,config:dict,root:Path,cache:Cache|None=None)->dict:
 episode.validate()
 if episode.id in {'.', '..'}:raise ValueError('Invalid episode identity')
 root.mkdir(parents=True,exist_ok=True);cache=cache or Cache(root/'cache');glossary=config.get('glossary',{})
 def settings(module,values:dict)->dict:return dict(values,implementation=digest(Path(module.__file__)))
 inputs=[Path(episode.local_file)] if episode.local_file else []
 a,x=cache.step('ingest',inputs,settings(ingest,{'episode':dataclasses.asdict(episode),'config':config['ingest']}),lambda o:ingest.execute(episode,o,config['ingest']));video=contained_path(a,x['video']);duration=x['duration'];sha=x['sha256']
 b,y=cache.step('separate',[video],settings(separate,config['separate']),lambda o:isolated('separate',o,[video,config['separate']],config['separate']['timeout']))
 c,z=cache.step('transcribe',[contained_path(b,y['vocals'])],settings(transcribe,dict(config['transcribe'],language=episode.language)),lambda o:isolated('transcribe',o,[contained_path(b,y['vocals']),config['transcribe'],episode.language],config['transcribe']['timeout']))
 d,t=cache.step('translate',[contained_path(c,z['segments'])],settings(translate,dict(config['translate'],glossary=glossary)),lambda o:isolated('translate',o,[contained_path(c,z['segments']),config['translate'],glossary],config['translate']['timeout']))
 e,v=cache.step('tts',[contained_path(d,t['translation'])],settings(tts,config['tts']),lambda o:isolated('tts',o,[contained_path(d,t['translation']),config['tts']],config['tts']['timeout']))
 f,w=cache.step('fit',[contained_path(e,v['voices']),*[contained_path(e,p['audio']) for p in read(contained_path(e,v['voices']))]],settings(fit,{'fit':config['fit'],'tts':config['tts'],'translate':config['translate'],'glossary':glossary,'duration':duration}),lambda o:isolated('fit',o,[contained_path(e,v['voices']),config['fit'],config['tts'],config['translate'],glossary,duration],config['fit']['timeout']))
 g,m=cache.step('mix',[video,contained_path(b,y['background']),contained_path(f,w['voice']),contained_path(f,w['segments'])],settings(mix,dict(config['mix'],provenance=episode.provenance,language=episode.language)),lambda o:isolated('mix',o,[video,contained_path(b,y['background']),contained_path(f,w['voice']),contained_path(f,w['segments']),config['mix'],episode.provenance,episode.language,duration],config['mix']['timeout']))
 h,q=cache.step('qa',[contained_path(g,m['video']),contained_path(g,m['audio']),contained_path(f,w['voice']),contained_path(f,w['segments'])],settings(qa,dict(config['qa'],asr=config['qa_asr'],original_duration=duration)),lambda o:isolated('qa',o,[contained_path(g,m['video']),contained_path(g,m['audio']),contained_path(f,w['voice']),contained_path(f,w['segments']),duration,config['qa'],config['qa_asr']],config['qa'].get('timeout',600)))
 destination=contained_path(root,('ready' if q['passed'] else 'review')+'/'+episode.id);destination.mkdir(parents=True,exist_ok=True);files={}
 for key,name in m.items():target=contained_path(destination,name);shutil.copy2(contained_path(g,name),target);files[key]=str(target)
 shutil.copy2(contained_path(h,'qa.json'),contained_path(destination,'qa.json'));shutil.copy2(contained_path(d,t['translation']),contained_path(destination,'translation.json'));save(contained_path(destination,'provenance.json'),dataclasses.asdict(episode))
 result={'episode':episode.id,'sha256':sha,'qa':q,'files':files,'steps':cache.events,'output':str(destination),'external_gpu_usd':0 if config['profile']=='local_cpu' else None,'tokens_paid':0,'test_profile':config['profile']};save(contained_path(destination,'result.json'),result);return result
