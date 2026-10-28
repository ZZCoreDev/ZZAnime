from __future__ import annotations
import re,unicodedata,wave
from pathlib import Path
from .core import media_info,read,save
from .transcribe import recognize
def words(text:str)->list[str]:return re.findall(r'\w+',unicodedata.normalize('NFKC',text).casefold())
def wer(reference:str,hypothesis:str)->float:
 a,b=words(reference),words(hypothesis)
 if not a:return 0 if not b else 1
 previous=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  row=[i]
  for j,y in enumerate(b,1):row.append(min(row[-1]+1,previous[j]+1,previous[j-1]+(x!=y)))
  previous=row
 return previous[-1]/len(a)
def decide(metrics:dict,config:dict)->list[str]:
 failures=[]
 for key,limit in [('out_of_time_fraction','max_out_of_time_fraction'),('wer','max_wer'),('duration_deviation','max_duration_deviation'),('clipping_fraction','max_clipping_fraction'),('speech_silence_seconds','max_speech_silence_seconds')]:
  if metrics[key]>config[limit]:failures.append(key)
 if metrics['segments']==0:failures.append('no_speech')
 return failures
def execute(video:Path,audio:Path,voice:Path,segments:Path,original_seconds:float,out:Path,config:dict,asr:dict)->dict:
 import numpy as np
 rows=read(segments);heard=recognize(audio,asr,'es');expected=' '.join(r['es'] for r in rows);actual=' '.join(r['text'] for r in heard)
 with wave.open(str(audio),'rb') as f:pcm=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
 with wave.open(str(voice),'rb') as f:rate=f.getframerate();speech=np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16).astype(np.float32)/32768
 silence=0.0
 for r in rows:
  chunk=speech[int(r['start']*rate):int((r['start']+r.get('fitted_seconds',0))*rate)];frame=max(1,rate//10);silent=0
  for i in range(0,len(chunk)-frame+1,frame):
   silent=silent+1 if np.sqrt(np.mean(chunk[i:i+frame]**2))<0.003 else 0;silence=max(silence,silent/10)
 metrics={'segments':len(rows),'out_of_time_fraction':sum(bool(r['out_of_time']) for r in rows)/len(rows) if rows else 1.0,'wer':wer(expected,actual),'duration_deviation':abs(media_info(video)['duration']-original_seconds)/original_seconds,'clipping_fraction':float(np.mean(np.abs(pcm)>=0.999)),'speech_silence_seconds':silence};reasons=decide(metrics,config);result={'passed':not reasons,'metrics':metrics,'review_reasons':reasons,'expected_es':expected,'recognized_es':actual,'qa_asr':asr['model']};save(out/'qa.json',result);return result
