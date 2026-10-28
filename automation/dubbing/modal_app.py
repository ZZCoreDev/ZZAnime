"""Only deploy after operator credentials, price cap and local proof are configured."""
from __future__ import annotations
import dataclasses,time
from pathlib import Path
import modal
image=(modal.Image.debian_slim(python_version='3.11').apt_install('ffmpeg','rubberband-cli','espeak-ng','libgomp1').pip_install_from_requirements('requirements-gpu.txt').add_local_python_source('dubpipe'))
app=modal.App('zzdub-authorized')
@app.function(image=image,gpu='L4',cpu=2,memory=16384,timeout=1200,startup_timeout=600,retries=0,max_containers=1,scaledown_window=2)
def run_episode(job:dict,config:dict)->dict:
 from dubpipe.core import Cache,Episode,digest
 from dubpipe.engine import execute
 from dubpipe.storage import Storage
 if not config.get('enabled') or config.get('max_gpu_usd_per_day',0)<=0:raise ValueError('Paid processing not authorized by config')
 storage=Storage();storage.require_lifecycle();root=Path('/tmp/zzdub');root.mkdir(exist_ok=True);source=root/'input.mp4';storage.get(job['input_key'],source)
 if digest(source)!=job['sha256']:raise ValueError('Source media hash mismatch')
 episode=Episode(**dict(job['episode'],local_file=str(source)));config['ingest']['allow_local_inputs']=True;start=time.monotonic();result=execute(episode,config,root,Cache(root/'cache',restore=storage.restore,checkpoint=storage.checkpoint));prefix=('ready/' if result['qa']['passed'] else 'review/')+job['sha256'];objects={}
 for name,file in result['files'].items():key=prefix+'/'+Path(file).name;storage.upload(Path(file),key);objects[name]=key
 for file in Path(result['output']).glob('*.json'):storage.upload(file,prefix+'/'+file.name)
 return {'episode':episode.id,'qa':result['qa'],'objects':objects,'artifact_prefix':prefix,'measured_function_seconds':time.monotonic()-start,'gpu_cost_is_estimate':True}
