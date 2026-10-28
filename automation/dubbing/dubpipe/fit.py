from __future__ import annotations
import wave
from pathlib import Path
from .core import canonical_hash,ffmpeg,read,run,save,wav_seconds
from . import translate,tts
def duration_ratio(source:float,window:float)->float:
 if source<=0 or window<=0:raise ValueError('Invalid phrase duration')
 return min(1.0,window/source)
def execute(voices:Path,out:Path,config:dict,tts_config:dict,translation_config:dict,glossary:dict,total_seconds:float)->dict:
 import numpy as np
 rows=read(voices);rate=48000;track=np.zeros(int(total_seconds*rate),dtype=np.float32);fitted=[];outside=0
 for row in rows:
  audio=voices.parent/row['audio'];window=row['end']-row['start'];seconds=wav_seconds(audio);ratio=duration_ratio(seconds,window);rewritten=False
  if ratio<1-config['max_duration_change'] and translation_config['backend']!='marian_cpu':
   key=canonical_hash({'row':row,'translation':translation_config,'voice':tts_config});rewrite=out/('rewrite-'+row['id']+'.json')
   if rewrite.exists() and read(rewrite).get('key')==key:new=read(rewrite)['row']
   else:new=translate.generate([dict(row,text=row['es'])],translation_config,glossary,shorten=True)[0];save(rewrite,{'key':key,'row':new})
   audio=out/('rewrite-'+row['id']+'.wav')
   if not audio.exists():tts.synthesize(new['es'],audio,tts_config)
   row=dict(row,es=new['es']);seconds=wav_seconds(audio);ratio=duration_ratio(seconds,window);rewritten=True
  bad=ratio<1-config['max_duration_change'] or row['start']<0 or row['end']>total_seconds+0.05
  item=dict(row,out_of_time=bad,rewrite_attempted=rewritten)
  if bad:outside+=1;item['fitted_seconds']=0;fitted.append(item);continue
  target=out/('fit-'+row['id']+'.wav');run([ffmpeg(),'-y','-i',audio,'-af','atempo='+str(1/ratio),'-ar',str(rate),'-ac','1','-c:a','pcm_s16le',target],config['timeout'])
  with wave.open(str(target),'rb') as f:pcm=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
  start=int(row['start']*rate);length=min(len(pcm),len(track)-start,int(window*rate));track[start:start+length]+=pcm[:length];item.update(fitted_seconds=length/rate,audio=target.name);fitted.append(item)
 with wave.open(str(out/'spanish_voice.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes((track.clip(-1,1)*32767).astype(np.int16).tobytes())
 save(out/'fitted.json',fitted);return {'voice':'spanish_voice.wav','segments':'fitted.json','outside_fraction':outside/len(rows) if rows else 1.0,'count':len(rows)}
