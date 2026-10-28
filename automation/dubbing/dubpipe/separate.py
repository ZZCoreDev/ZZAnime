from __future__ import annotations
import os,shutil,sys
from pathlib import Path
from .core import ffmpeg,run
def execute(video:Path,out:Path,config:dict)->dict:
 audio=out/'original.wav';run([ffmpeg(),'-y','-i',video,'-vn','-ar','44100','-ac','2','-c:a','pcm_s16le',audio],config['timeout'])
 # Give Demucs an actual ffmpeg executable on Windows without modifying system PATH.
 env_path=os.environ.get('PATH','');binary=Path(ffmpeg());os.environ['PATH']=str(binary.parent)+os.pathsep+env_path
 try:
  import torch,torchaudio
  from demucs.pretrained import get_model
  from demucs.apply import apply_model
  import numpy as np,wave
  with wave.open(str(audio),'rb') as f:rate=f.getframerate();channels=f.getnchannels();data=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).copy().reshape(-1,channels).T.astype(np.float32)/32768
  model=get_model(config['model']);model.to(config['device']);model.eval();torch.set_num_threads(config.get('cpu_threads',2));tensor=torch.from_numpy(data).to(config['device']);reference=tensor.mean(0);mean=reference.mean();std=reference.std().clamp(min=1e-8);tensor=(tensor-mean)/std
  with torch.inference_mode():stems=apply_model(model,tensor[None],device=config['device'],shifts=0,split=True,overlap=0.1,progress=False)[0]*std+mean
  voice=stems[model.sources.index('vocals')];background=stems.sum(0)-voice
  for name,values in [('vocals.wav',voice),('background.wav',background)]:
   pcm=(values.detach().cpu().numpy().T.clip(-1,1)*32767).astype(np.int16)
   with wave.open(str(out/name),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes(pcm.tobytes())
  del model,stems,tensor
  if config['device']=='cuda':torch.cuda.empty_cache()
 finally:os.environ['PATH']=env_path
 return {'original':'original.wav','vocals':'vocals.wav','background':'background.wav','model':config['model']}
