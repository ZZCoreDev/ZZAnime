from __future__ import annotations
import datetime,math,subprocess,time
from pathlib import Path
from .core import read,save
class State:
 def __init__(self,path:Path,git_dir:Path|None=None):self.path=path;self.git_dir=git_dir;self.data=read(path) if path.exists() else {'schema':1,'episodes':{},'reservations':[]}
 def commit(self)->None:
  save(self.path,self.data)
  if self.git_dir:
   relative=self.path.resolve().relative_to(self.git_dir.resolve());args=['git','-C',str(self.git_dir)];subprocess.run(args+['add','--',str(relative)],check=True,capture_output=True)
   p=subprocess.run(args+['diff','--cached','--quiet'],capture_output=True)
   if p.returncode:
    subprocess.run(args+['commit','-m','Checkpoint dubbing state'],check=True,capture_output=True);subprocess.run(args+['push','origin','HEAD:dubbing-state'],check=True,capture_output=True)
 def reserve(self,episode:str,amount:float,cap:float)->None:
  day=datetime.datetime.now(datetime.timezone.utc).date().isoformat();used=sum(r['usd'] for r in self.data['reservations'] if r['day']==day)
  if not math.isfinite(amount) or not math.isfinite(cap) or amount<=0 or cap<=0 or used+amount>cap:raise ValueError('GPU daily budget exhausted or disabled')
  self.data['reservations'].append({'episode':episode,'day':day,'usd':amount,'at':time.time()});self.commit()
 def status(self,episode:str,status:str,**fields)->None:
  row=self.data['episodes'].get(episode,{});row.update(status=status,updated_at=time.time(),**fields);self.data['episodes'][episode]=row;self.commit()
 def done(self,episode:str)->bool:return self.data['episodes'].get(episode,{}).get('status') in {'uploaded','duplicate','review','blocked','publish_uncertain','dispatch_uncertain'}
