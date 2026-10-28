from __future__ import annotations
from pathlib import Path
from .core import save
def recognize(audio:Path,config:dict,language:str)->list[dict]:
 if config['backend']=='whisperx':
  import whisperx,torch
  model=whisperx.load_model(config['model'],config['device'],compute_type=config['compute_type'],language=language);samples=whisperx.load_audio(str(audio));result=model.transcribe(samples,batch_size=config.get('batch_size',4));del model
  if result['segments']:
   align,metadata=whisperx.load_align_model(language_code=language,device=config['device']);result=whisperx.align(result['segments'],align,metadata,samples,config['device'],return_char_alignments=False);del align
  segments=result['segments']
  if config.get('diarize'):
   import os
   from whisperx.diarize import DiarizationPipeline
   if not os.getenv('HF_TOKEN'):raise ValueError('Optional diarization requires an authorized HF_TOKEN')
   diarizer=DiarizationPipeline(token=os.environ['HF_TOKEN'],device=config['device']);result=whisperx.assign_word_speakers(diarizer(samples),result);segments=result['segments'];del diarizer
  if config['device']=='cuda':torch.cuda.empty_cache()
 else:
  from faster_whisper import WhisperModel
  model=WhisperModel(config['model'],device=config['device'],compute_type=config['compute_type'],cpu_threads=config.get('cpu_threads',2));stream,_=model.transcribe(str(audio),language=language,beam_size=5,vad_filter=True,condition_on_previous_text=False);segments=[{'start':s.start,'end':s.end,'text':s.text} for s in stream];del model
 return [{'id':str(i),'start':float(s['start']),'end':float(s['end']),'text':s['text'].strip(),'speaker':s.get('speaker','default')} for i,s in enumerate(segments) if s.get('text','').strip() and s['end']>s['start']]
def execute(audio:Path,out:Path,config:dict,language:str)->dict:
 segments=recognize(audio,config,language);save(out/'segments.json',segments);return {'segments':'segments.json','count':len(segments),'language':language,'model':config['model']}
