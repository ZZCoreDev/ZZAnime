from __future__ import annotations
import dataclasses,os,shutil,subprocess,sys,time
from pathlib import Path
from . import ingest,separate,transcribe,translate,tts,fit,mix,qa
from .core import Cache,Episode,digest,read,save
def isolated(name:str,out:Path,args:list,timeout:int)->dict:
 request=out/'worker-request.json';save(request,{'step':name,'out':str(out),'args':[str(x) if isinstance(x,Path) else x for x in args]});env=dict(os.environ);env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])+os.pathsep+env.get('PYTHONPATH','')
 process=subprocess.run([sys.executable,'-X','utf8','-m','dubpipe.step_worker',str(request)],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout);(out/'worker.log').write_text(process.stdout+'\n'+process.stderr,encoding='utf-8')
 if process.returncode:raise RuntimeError(name+' failed; inspect '+str(out/'worker.log'))
 return read(out/'worker-result.json')
def execute(episode:Episode,config:dict,root:Path,cache:Cache|None=None)->dict:
 root.mkdir(parents=True,exist_ok=True);cache=cache or Cache(root/'cache');glossary=config.get('glossary',{})
 def settings(module,values:dict)->dict:return dict(values,implementation=digest(Path(module.__file__)))
 inputs=[Path(episode.local_file)] if episode.local_file else []
 a,x=cache.step('ingest',inputs,settings(ingest,{'episode':dataclasses.asdict(episode),'config':config['ingest']}),lambda o:ingest.execute(episode,o,config['ingest']));video=a/x['video'];duration=x['duration'];sha=x['sha256']
 b,y=cache.step('separate',[video],settings(separate,config['separate']),lambda o:isolated('separate',o,[video,config['separate']],config['separate']['timeout']))
 c,z=cache.step('transcribe',[b/y['vocals']],settings(transcribe,dict(config['transcribe'],language=episode.language)),lambda o:isolated('transcribe',o,[b/y['vocals'],config['transcribe'],episode.language],config['transcribe']['timeout']))
 d,t=cache.step('translate',[c/z['segments']],settings(translate,dict(config['translate'],glossary=glossary)),lambda o:isolated('translate',o,[c/z['segments'],config['translate'],glossary],config['translate']['timeout']))
 e,v=cache.step('tts',[d/t['translation']],settings(tts,config['tts']),lambda o:isolated('tts',o,[d/t['translation'],config['tts']],config['tts']['timeout']))
 f,w=cache.step('fit',[e/v['voices'],*[e/p['audio'] for p in read(e/v['voices'])]],settings(fit,{'fit':config['fit'],'tts':config['tts'],'translate':config['translate'],'glossary':glossary,'duration':duration}),lambda o:isolated('fit',o,[e/v['voices'],config['fit'],config['tts'],config['translate'],glossary,duration],config['fit']['timeout']))
 g,m=cache.step('mix',[video,b/y['background'],f/w['voice'],f/w['segments']],settings(mix,dict(config['mix'],provenance=episode.provenance,language=episode.language)),lambda o:isolated('mix',o,[video,b/y['background'],f/w['voice'],f/w['segments'],config['mix'],episode.provenance,episode.language,duration],config['mix']['timeout']))
 h,q=cache.step('qa',[g/m['video'],g/m['audio'],f/w['voice'],f/w['segments']],settings(qa,dict(config['qa'],asr=config['qa_asr'],original_duration=duration)),lambda o:isolated('qa',o,[g/m['video'],g/m['audio'],f/w['voice'],f/w['segments'],duration,config['qa'],config['qa_asr']],config['qa'].get('timeout',600)))
 destination=root/('ready' if q['passed'] else 'review')/episode.id;destination.mkdir(parents=True,exist_ok=True);files={}
 for key,name in m.items():shutil.copy2(g/name,destination/name);files[key]=str(destination/name)
 shutil.copy2(h/'qa.json',destination/'qa.json');shutil.copy2(d/t['translation'],destination/'translation.json');save(destination/'provenance.json',dataclasses.asdict(episode))
 result={'episode':episode.id,'sha256':sha,'qa':q,'files':files,'steps':cache.events,'output':str(destination),'external_gpu_usd':0 if config['profile']=='local_cpu' else None,'tokens_paid':0,'test_profile':config['profile']};save(destination/'result.json',result);return result
