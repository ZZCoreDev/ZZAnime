"""Real CPU proof: CC clip + synthetic English test narration, never a Japanese-production benchmark."""
from __future__ import annotations
import dataclasses,json,os,sys,time,zipfile
from pathlib import Path
import yaml
from dubpipe.core import Episode,canonical_hash,download,ffmpeg,run,save
from dubpipe.engine import execute
from dubpipe import tts,publish,notify
from dubpipe.qa import wer
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];WORK=ROOT/'work/dubbing-demo'
def main()->None:
 WORK.mkdir(parents=True,exist_ok=True);config=yaml.safe_load((HERE/'config.yml').read_text(encoding='utf-8'));config.update(profile='local_cpu',enabled=True,max_gpu_usd_per_day=0)
 config['ingest'].update(allow_local_inputs=True,max_episode_seconds=90,max_download_mb=250);config['separate'].update(device='cpu',timeout=600);config['transcribe'].update(backend='faster_whisper',model='tiny.en',device='cpu',compute_type='int8',timeout=601);config['translate'].update(backend='marian_cpu',model='Helsinki-NLP/opus-mt-en-es',device='cpu');config['qa_asr'].update(model='base',device='cpu',compute_type='int8');config['tts']['model_cache']=str(WORK/'models');config['glossary']=yaml.safe_load((HERE/'glossary/big-buck-bunny.yml').read_text(encoding='utf-8'))
 os.environ['HF_HOME']=str(WORK/'models/huggingface');os.environ['TORCH_HOME']=str(WORK/'models/torch');os.environ['HF_HUB_DISABLE_XET']='1'
 narration='Hello. This is a test of automatic dubbing. We keep the original music.';signature=canonical_hash({'fixture':1,'narration':narration,'seconds':24,'source':'Big Buck Bunny CC-BY-3.0'});source=WORK/('input-'+signature[:16]+'.mp4');start=time.monotonic()
 if not source.exists():
  archive=WORK/'bbb-original.zip'
  if not archive.exists():download('https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_320x180.mp4.zip',archive,['download.blender.org'],250*1024*1024)
  movie=WORK/'bbb-original.mp4'
  if not movie.exists():
   with zipfile.ZipFile(archive) as z:
    matches=[x for x in z.infolist() if x.filename.lower().endswith('.mp4') and not x.is_dir()]
    if len(matches)!=1 or matches[0].file_size>250*1024*1024:raise ValueError('Unexpected CC archive')
    with z.open(matches[0]) as f,movie.open('wb') as out:__import__('shutil').copyfileobj(f,out)
  english=dict(config['tts'],length_scale=1.25);tts.synthesize(narration,WORK/'test-narration.en.wav',english,'en')
  run([ffmpeg(),'-y','-i',movie,'-i',WORK/'test-narration.en.wav','-filter_complex','[0:a]volume=0.22[bg];[1:a]adelay=2000|2000[v];[bg][v]amix=inputs=2:duration=first:normalize=0[a]','-map','0:v:0','-map','[a]','-t','24','-c:v','libx264','-preset','fast','-crf','23','-c:a','aac','-movflags','+faststart',source],600)
 provenance={'authorized':True,'creator':'(c) 2008 Blender Foundation / www.bigbuckbunny.org','license':'CC-BY-3.0','license_url':'https://creativecommons.org/licenses/by/3.0/','source_url':'https://peach.blender.org/about/','additional_credits':'Fragmento CC con narración sintética de prueba añadida. No es doblaje japonés de producción. Voz ES: Spanish Harvard corpus, CC BY 3.0, https://datashare.ed.ac.uk/handle/10283/574. Modelos Piper: https://huggingface.co/rhasspy/piper-voices','made_for_kids':False}
 episode=Episode('cc-local-demo-'+signature[:12],'big-buck-bunny','Prueba local CC · doblaje español','https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_320x180.mp4.zip','en',provenance,local_file=str(source));save(WORK/'demo-config.json',config)
 result=execute(episode,config,WORK);out=Path(result['output']);publication=publish.execute(episode,{k:Path(v) for k,v in result['files'].items()},result['sha256'],out,{'enabled':False});source_text=' '.join(r['text'] for r in json.loads((out/'translation.json').read_text(encoding='utf-8')));source_wer=wer(narration,source_text);summary={'source_asr_wer':source_wer,'source_transcription_complete':source_wer<=0.15,'profile':'local_cpu','qa_passed':result['qa']['passed'] and source_wer<=0.15,'output':result['files']['video'],'qa':result['qa'],'elapsed_seconds':round(time.monotonic()-start,2),'gpu_seconds':0,'external_gpu_usd':0,'paid_llm_tokens':0,'uploaded':False,'publish_preview':publication,'production_japanese_validated':False,'local_electricity_cost_measured':False,'steps':result['steps']};notify.execute(summary,WORK);save(WORK/'completion.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
