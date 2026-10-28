from __future__ import annotations
import wave
from pathlib import Path
from .core import download,read,save
def voice_path(config:dict,language:str='es')->Path:
 root=Path(config['model_cache']);root.mkdir(parents=True,exist_ok=True);voice=config['voices'][language];name=voice['name'];path=root/(name+'.onnx')
 for suffix in ['.onnx','.onnx.json']:
  target=root/(name+suffix)
  if not target.exists():download(voice['base_url']+'/'+name+suffix,target,['huggingface.co','cdn-lfs.hf.co','cdn-lfs-us-1.hf.co','cas-bridge.xethub.hf.co','us.aws.cdn.hf.co'],100*1024*1024)
 card=root/(name+'.MODEL_CARD.txt')
 if not card.exists():download(voice['base_url'].replace('/resolve/','/raw/')+'/MODEL_CARD',card,['huggingface.co'],1024*1024)
 return path
def synthesize(text:str,target:Path,config:dict,language:str='es')->None:
 from piper import PiperVoice,SynthesisConfig
 voice=PiperVoice.load(str(voice_path(config,language)));target.parent.mkdir(parents=True,exist_ok=True)
 with wave.open(str(target),'wb') as f:voice.synthesize_wav(text,f,syn_config=SynthesisConfig(length_scale=config.get('length_scale',1.0)))
def execute(translation:Path,out:Path,config:dict)->dict:
 rows=read(translation);result=[]
 for row in rows:
  filename='voice-'+row['id']+'.wav';synthesize(row['es'],out/filename,config);result.append(dict(row,audio=filename))
 save(out/'voices.json',result);return {'voices':'voices.json','count':len(result),'voice_mode':'configured generic voice; no speaker cloning'}
