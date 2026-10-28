from __future__ import annotations
from pathlib import Path
from .core import ffmpeg,read,run
def stamp(value:float)->str:
 ms=max(0,round(value*1000));return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
def execute(video:Path,background:Path,voice:Path,segments:Path,out:Path,config:dict,provenance:dict,language:str,total_seconds:float)->dict:
 rows=read(segments);srt='\n\n'.join(f'{i+1}\n{stamp(r["start"])} --> {stamp(r["end"])}\n{r["es"]}' for i,r in enumerate(rows));(out/'subtitles.es.srt').write_text(srt+'\n',encoding='utf-8')
 credit=f'{provenance["creator"]} | {provenance.get("license", "operator-authorized")} | {provenance["source_url"]} | Doblaje automático al español; audio alterado.'
 (out/'ATTRIBUTION.txt').write_text(credit+'\n',encoding='utf-8');filter='[0:a]aformat=channel_layouts=stereo[bg];[1:a]asplit[vo][side];[bg][side]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=300[duck];[duck][vo]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad[es]'
 run([ffmpeg(),'-y','-i',background,'-i',voice,'-filter_complex',filter,'-map','[es]','-t',str(total_seconds),'-ar','48000','-ac','2','-c:a','pcm_s16le',out/'spanish_mix.wav'],config['timeout'])
 run([ffmpeg(),'-y','-i',video,'-i',out/'spanish_mix.wav','-i',out/'subtitles.es.srt','-map','0:v:0','-map','1:a:0','-map','0:a:0','-map','2:0','-c:v','copy','-c:a','aac','-b:a','160k','-c:s','mov_text','-metadata:s:a:0','language=spa','-metadata:s:a:0','title=Español · doblaje automático','-metadata:s:a:1','language='+({'ja':'jpn','en':'eng'}.get(language,'und')),'-metadata:s:s:0','language=spa','-disposition:a:0','default','-disposition:a:1','0','-metadata','comment='+credit,'-movflags','+faststart','-t',str(total_seconds),out/'dubbed.es.mp4'],config['timeout'])
 run([ffmpeg(),'-y','-ss','1','-i',video,'-frames:v','1','-vf','scale=640:-2',out/'thumbnail.jpg'],config['timeout'])
 return {'video':'dubbed.es.mp4','audio':'spanish_mix.wav','srt':'subtitles.es.srt','attribution':'ATTRIBUTION.txt','thumbnail':'thumbnail.jpg'}
