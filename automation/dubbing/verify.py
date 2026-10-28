"""One local verification command. --demo runs real CPU inference, never GPU/upload."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'work/dubbing-validation'
def main()->None:
 p=argparse.ArgumentParser();p.add_argument('--demo',action='store_true');args=p.parse_args();OUT.mkdir(exist_ok=True);env=dict(os.environ,PYTHONPATH=str(HERE));steps=[]
 commands=[('compile',[sys.executable,'-m','compileall','-q',str(HERE/'dubpipe'),str(HERE/'modal_app.py')]),('tests',[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-v']),('doctor',[sys.executable,'-X','utf8','-m','dubpipe.cli','doctor'])]
 if args.demo:commands.append(('demo',[sys.executable,'-X','utf8',str(HERE/'demo.py')]))
 for label,command in commands:
  started=time.monotonic();r=subprocess.run(command,cwd=HERE,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=1800);(OUT/(label+'.log')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8');steps.append({'step':label,'exit_code':r.returncode,'seconds':round(time.monotonic()-started,2)})
  if r.returncode:save={'passed':False,'steps':steps};(OUT/'verification.json').write_text(json.dumps(save,indent=2));raise SystemExit('FALLO: '+label+'; '+str(OUT/(label+'.log')))
 if args.demo:
  from dubpipe.core import media_info,digest,run,ffmpeg
  proof=json.loads((ROOT/'work/dubbing-demo/completion.json').read_text(encoding='utf-8'));video=Path(proof['output']);info=media_info(video)
  if not proof['qa_passed'] or not proof['source_transcription_complete'] or info['audio_streams']!=2:raise SystemExit('FALLO: prueba de audio/QA incompleta')
  run([ffmpeg(),'-v','error','-i',video,'-map','0:v:0','-map','0:a','-f','null','-'],120);proof.update(output_sha256=digest(video),video_streams_verified=info['video_streams'],audio_streams_verified=info['audio_streams']);(OUT/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'verification.json').write_text(json.dumps({'passed':True,'steps':steps,'gpu_invoked':False,'uploaded':False},indent=2),encoding='utf-8');print('PASS: '+', '.join(x['step'] for x in steps)+'; GPU0; upload disabled; '+str(OUT/'verification.json'))
if __name__=='__main__':main()
