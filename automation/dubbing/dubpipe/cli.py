from __future__ import annotations
import argparse,dataclasses,datetime,json,os,shutil,sys,time
from pathlib import Path
import yaml
from . import ingest,notify,publish
from .core import Cache,Episode,canonical_hash,read,save
from .state import State
from .storage import Storage

REQUIRED=['MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','S3_BUCKET','S3_ACCESS_KEY_ID','S3_SECRET_ACCESS_KEY','YOUTUBE_OAUTH_JSON']
def doctor(config:dict)->dict:
 missing=[x for x in REQUIRED if not os.getenv(x)];budget=config.get('max_gpu_usd_per_day',0);return {'configured':not missing and budget>0 and config.get('enabled',False) and config.get('publish',{}).get('enabled',False),'missing_secret_names':missing,'daily_gpu_usd':budget,'enabled':config.get('enabled',False),'sources':'authorized direct files only','voice_cloning':False,'cron_requires':'ZZ_DUBBING_ENABLED=true after real proof','secrets_values_printed':False}
def worst_case_gpu_usd(config:dict)->float:
 checked=datetime.date.fromisoformat(config['gpu_rate_checked'])
 age=(datetime.datetime.now(datetime.timezone.utc).date()-checked).days
 if age<0 or age>30:raise ValueError('GPU price assumptions need refreshing before paid execution')
 if not 0<config['max_gpu_seconds']<=1200 or config['gpu_startup_seconds']<600 or config['gpu_rate_usd_per_second']<0.000222:raise ValueError('GPU reservation below fixed runtime/rate assumptions')
 return round((config['max_gpu_seconds']+config['gpu_startup_seconds']+30)*config['gpu_rate_usd_per_second'],6)
def scheduled_time(state:State,config:dict)->str:
 now=datetime.datetime.now(datetime.timezone.utc);first=now+datetime.timedelta(minutes=config['first_publish_delay_minutes']);existing=[datetime.datetime.fromisoformat(r['publish_at']) for r in state.data['episodes'].values() if r.get('publish_at')]
 if existing:first=max(first,max(existing)+datetime.timedelta(minutes=config['window_minutes']))
 return first.isoformat().replace('+00:00','Z')
def process(config:dict,sources:dict,root:Path,state:State)->dict:
 if not doctor(config)['configured']:raise ValueError('Live execution disabled or missing required secret names; run doctor')
 if not config['publish'].get('enabled'):raise ValueError('YouTube publication remains explicitly disabled')
 import modal
 storage=Storage();storage.require_lifecycle();episodes=ingest.discover(sources,config['ingest'],root/'feeds');summary={'uploaded':[],'review':[],'blocked':[],'failed':[],'estimated_gpu_usd_reserved':0.0,'actual_invoice_usd':None,'paid_llm_tokens':0};count=0
 for episode in episodes:
  previous=state.data['episodes'].get(episode.id,{})
  if previous.get('retry_after',0)>time.time():continue
  if previous.get('status') in {'publish_pending','publish_uncertain'}:
   try:
    recovered=publish.reconcile(previous['sha256'])
    if recovered:state.status(episode.id,'uploaded',**recovered);summary['uploaded'].append(recovered)
   except Exception as error:summary['failed'].append({'episode':episode.id,'reason':'reconciliation:'+type(error).__name__})
   continue
  if state.done(episode.id):continue
  if count>=config['max_episodes_per_run']:break
  count+=1
  try:
   episode.validate();work=root/episode.id;work.mkdir(parents=True,exist_ok=True)
   glossary=Path('glossary')/(episode.series+'.yml');episode_config=dict(config,glossary=yaml.safe_load(glossary.read_text(encoding='utf-8')) if glossary.exists() else {})
   if previous.get('status')=='dispatch_pending' and not previous.get('call_id'):state.status(episode.id,'dispatch_uncertain',error='Dispatch acknowledgement missing; no second GPU invocation');continue
   if previous.get('call_id'):
    call=modal.FunctionCall.from_id(previous['call_id']);sha=previous['sha256']
   else:
    cache=Cache(root/'ingest-cache');folder,record=cache.step('ingest',[],{'episode':dataclasses.asdict(episode),'config':config['ingest']},lambda o:ingest.execute(episode,o,config['ingest']));sha=record['sha256']
    duplicate=next((r for key,r in state.data['episodes'].items() if key!=episode.id and r.get('sha256')==sha and r.get('status')=='uploaded'),None)
    if duplicate:state.status(episode.id,'duplicate',sha256=sha,url=duplicate['url']);continue
    amount=worst_case_gpu_usd(config);state.reserve(episode.id,amount,config['max_gpu_usd_per_day']);summary['estimated_gpu_usd_reserved']+=amount;key='inputs/'+sha+'.mp4';storage.upload(folder/record['video'],key);state.status(episode.id,'dispatch_pending',sha256=sha)
    secrets={k:os.environ[k] for k in ['S3_BUCKET','S3_ACCESS_KEY_ID','S3_SECRET_ACCESS_KEY','S3_ENDPOINT','S3_REGION'] if os.getenv(k)}
    function=modal.Function.from_name('zzdub-authorized','run_episode').with_options(timeout=config['max_gpu_seconds'],secrets=[modal.Secret.from_dict(secrets)]);call=function.spawn({'episode':dataclasses.asdict(episode),'input_key':key,'sha256':sha},episode_config);state.status(episode.id,'gpu_running',call_id=call.object_id,sha256=sha)
   result=call.get(timeout=config['max_gpu_seconds']+config['gpu_startup_seconds']+120);save(work/'worker-result.json',result)
   if not result['qa']['passed']:state.status(episode.id,'review',sha256=sha,qa=result['qa'],artifact_prefix=result['artifact_prefix']);summary['review'].append(episode.id);continue
   files={}
   for name,key in result['objects'].items():path=work/Path(key).name;storage.get(key,path);files[name]=path
   publish_at=scheduled_time(state,config['publish']);state.status(episode.id,'publish_pending',sha256=sha,publish_at=publish_at);receipt=publish.execute(episode,files,sha,work,config['publish'],publish_at);receipt.pop('status',None);state.status(episode.id,'uploaded',sha256=sha,series=episode.series,publish_at=publish_at,**receipt);summary['uploaded'].append(receipt)
  except Exception as error:
   current=state.data['episodes'].get(episode.id,{})
   if current.get('status') in {'publish_pending','publish_uncertain'}:status='publish_uncertain'
   elif current.get('status')=='dispatch_pending':status='dispatch_uncertain'
   elif isinstance(error,ValueError) and 'budget' not in str(error).lower():status='blocked'
   else:status='failed'
   import urllib.error
   delay=0
   if isinstance(error,urllib.error.HTTPError) and error.code in {403,429}:
    try:delay=max(3600,int(error.headers.get('Retry-After','3600')))
    except ValueError:delay=86400
   state.status(episode.id,status,error=type(error).__name__,message=str(error)[:240] if isinstance(error,ValueError) else 'See local execution log; no credentials are logged',retry_after=time.time()+delay);summary['blocked' if status=='blocked' else 'failed'].append({'episode':episode.id,'reason':type(error).__name__})
   if 'budget' in str(error).lower():break
 links=[{'episode':key,'series':row.get('series',''),'url':row['url'],'sha256':row.get('sha256'),'language':'es','provider':'youtube_official'} for key,row in state.data['episodes'].items() if row.get('status')=='uploaded'];save(state.path.parent/'published-links.json',links);notify.execute(summary,root);return summary
def main()->None:
 p=argparse.ArgumentParser();p.add_argument('action',choices=['doctor','run']);p.add_argument('--require-live',action='store_true');p.add_argument('--config',type=Path,default=Path('config.yml'));p.add_argument('--sources',type=Path,default=Path('sources.yml'));p.add_argument('--root',type=Path,default=Path('runtime'));p.add_argument('--state',type=Path,default=Path('state/processed.json'));p.add_argument('--state-git-dir',type=Path);args=p.parse_args();config=yaml.safe_load(args.config.read_text(encoding='utf-8'))
 if args.action=='doctor':
  report=doctor(config);print(json.dumps(report,ensure_ascii=False))
  if args.require_live and not report['configured']:raise SystemExit(2)
  return
 args.root.mkdir(parents=True,exist_ok=True);print(json.dumps(process(config,yaml.safe_load(args.sources.read_text(encoding='utf-8')),args.root,State(args.state,args.state_git_dir)),ensure_ascii=False))
if __name__=='__main__':main()
