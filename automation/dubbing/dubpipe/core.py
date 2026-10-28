from __future__ import annotations
import dataclasses,hashlib,json,os,re,shutil,subprocess,time,urllib.error,urllib.parse,urllib.request,wave
from pathlib import Path
from typing import Any,Callable

@dataclasses.dataclass(frozen=True)
class Episode:
 id:str
 series:str
 title:str
 url:str
 language:str
 provenance:dict[str,Any]
 archive_member:str=''
 local_file:str=''
 def validate(self)->None:
  if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,120}',self.id) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}',self.series):raise ValueError('Invalid episode/series identity')
  if self.language not in {'ja','en','es'}:raise ValueError('Unsupported source language')
  if not self.provenance.get('authorized') or not self.provenance.get('creator') or not self.provenance.get('source_url'):raise ValueError('Source provenance requires review')
  if not self.title.strip():raise ValueError('Title missing')

def digest(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def canonical_hash(value:Any)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def save(path:Path,data:Any)->None:
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
def read(path:Path)->Any:return json.loads(path.read_text(encoding='utf-8'))
def ffmpeg()->str:
 if os.getenv('FFMPEG_BINARY'):return os.environ['FFMPEG_BINARY']
 if found:=shutil.which('ffmpeg'):return found
 import imageio_ffmpeg
 return imageio_ffmpeg.get_ffmpeg_exe()
def run(args:list[str|Path],timeout:int=600)->str:
 if str(args[0])==ffmpeg():
  protected=[]
  for arg in args:
   if str(arg)=='-i':protected+=['-protocol_whitelist','file,pipe']
   protected.append(arg)
  args=protected
 result=subprocess.run([str(a) for a in args],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 if result.returncode:raise RuntimeError('Command failed: '+str(args[0])+'\n'+result.stderr[-4000:])
 return result.stderr
def media_info(path:Path)->dict[str,Any]:
 p=subprocess.run([ffmpeg(),'-hide_banner','-protocol_whitelist','file,pipe','-i',str(path)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30);m=re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)',p.stderr)
 if not m:raise ValueError('Media duration unavailable')
 return {'duration':int(m[1])*3600+int(m[2])*60+float(m[3]),'audio_streams':len(re.findall(r'Stream #.*?Audio:',p.stderr)),'video_streams':len(re.findall(r'Stream #.*?Video:',p.stderr))}
def wav_seconds(path:Path)->float:
 with wave.open(str(path),'rb') as f:return f.getnframes()/f.getframerate()
def download(url:str,target:Path,hosts:list[str],max_bytes:int)->None:
 def allowed(value:str)->bool:
  u=urllib.parse.urlsplit(value)
  return u.scheme=='https' and u.hostname in hosts and not u.username and not u.password and u.port in {None,443}
 class Redirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,msg,headers,newurl):
   if not allowed(newurl):raise ValueError('Redirect outside explicit source allowlist')
   return super().redirect_request(req,fp,code,msg,headers,newurl)
 if not allowed(url):raise ValueError('Unapproved direct download host')
 target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix(target.suffix+'.part')
 for attempt in range(3):
  try:
   with urllib.request.build_opener(Redirect()).open(urllib.request.Request(url,headers={'User-Agent':'ZZDub/0.1'}),timeout=60) as response,tmp.open('wb') as f:
    total=0
    for block in iter(lambda:response.read(1024*1024),b''):
     total+=len(block)
     if total>max_bytes:raise ValueError('Download size limit')
     f.write(block)
   tmp.replace(target);return
  except Exception as error:
   if isinstance(error,urllib.error.HTTPError) and error.code in {401,403,429}:raise
   if isinstance(error,ValueError) or attempt==2:raise
   time.sleep(2**attempt)

class Cache:
 def __init__(self,root:Path,restore:Callable[[str,Path],None]|None=None,checkpoint:Callable[[str,Path],None]|None=None):self.root=root;self.restore=restore;self.checkpoint=checkpoint;self.events:list[dict[str,Any]]=[]
 def step(self,name:str,inputs:list[Path],settings:dict[str,Any],action:Callable[[Path],dict[str,Any]])->tuple[Path,dict[str,Any]]:
  key=canonical_hash({'version':1,'step':name,'files':[digest(p) for p in inputs],'settings':settings});folder=self.root/key;manifest=folder/'manifest.json'
  if not manifest.exists() and self.restore:self.restore(key,folder)
  if manifest.exists():
   m=read(manifest)
   safe=all((folder/p).resolve().is_relative_to(folder.resolve()) for p in m['artifacts'])
   safe=safe and all(not isinstance(m['result'].get(k),str) or m['result'][k] in m['artifacts'] for k in ['video','original','vocals','background','segments','translation','voices','voice','audio','srt','thumbnail','attribution'] if k in m['result'])
   if safe and m.get('key')==key and all((folder/p).is_file() and digest(folder/p)==h for p,h in m['artifacts'].items()):self.events.append({'step':name,'cached':True,'seconds':0,'original_compute_seconds':m.get('compute_seconds')});return folder,m['result']
  folder.mkdir(parents=True,exist_ok=True);start=time.monotonic();result=action(folder);files={str(p.relative_to(folder)):digest(p) for p in folder.rglob('*') if p.is_file() and p.name!='manifest.json'}
  elapsed=round(time.monotonic()-start,3);save(manifest,{'key':key,'step':name,'createdAt':time.time(),'artifacts':files,'result':result,'compute_seconds':elapsed});self.events.append({'step':name,'cached':False,'seconds':elapsed})
  if self.checkpoint:self.checkpoint(key,folder)
  return folder,result
