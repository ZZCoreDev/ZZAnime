"""An allowlisted ML subprocess per step provides enforceable Windows/Linux timeouts."""
from __future__ import annotations
import sys
from pathlib import Path
from . import separate,transcribe,translate,tts,fit,mix,qa
from .core import read,save
def main()->None:
 request=read(Path(sys.argv[1]));name=request['step'];args=request['args'];out=Path(request['out'])
 if name=='separate':result=separate.execute(Path(args[0]),out,args[1])
 elif name=='transcribe':result=transcribe.execute(Path(args[0]),out,args[1],args[2])
 elif name=='translate':result=translate.execute(Path(args[0]),out,args[1],args[2])
 elif name=='tts':result=tts.execute(Path(args[0]),out,args[1])
 elif name=='fit':result=fit.execute(Path(args[0]),out,*args[1:])
 elif name=='mix':result=mix.execute(*[Path(x) for x in args[:4]],out,*args[4:])
 elif name=='qa':result=qa.execute(*[Path(x) for x in args[:4]],args[4],out,*args[5:])
 else:raise ValueError('Unknown worker stage')
 save(out/'worker-result.json',result)
if __name__=='__main__':main()
