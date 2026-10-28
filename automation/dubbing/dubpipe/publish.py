from __future__ import annotations
import datetime,json,os,time
from pathlib import Path
from .core import Episode,read,save
def metadata(episode:Episode,sha256:str,publish_at:str|None=None)->dict:
 p=episode.provenance;description=f'{episode.title}\nDoblaje automático al español. Audio generado y adaptado.\n\nFuente: {p["source_url"]}\nAutor: {p["creator"]}\nLicencia/autorización: {p.get("license","autorización del operador")}\n{p.get("license_url","")}\n{p.get("additional_credits","")}'
 status={'privacyStatus':'private','selfDeclaredMadeForKids':bool(p.get('made_for_kids',False)),'containsSyntheticMedia':True}
 if publish_at:status['publishAt']=publish_at
 return {'snippet':{'title':(episode.title+' · Español · doblaje automático')[:100],'description':description,'categoryId':'1','defaultLanguage':'es','tags':['zzdub:'+sha256,episode.series]},'status':status}
def client():
 from google.oauth2.credentials import Credentials
 from googleapiclient.discovery import build
 value=json.loads(os.environ['YOUTUBE_OAUTH_JSON']);credentials=Credentials.from_authorized_user_info(value,scopes=['https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.force-ssl']);return build('youtube','v3',credentials=credentials,cache_discovery=False)
def reconcile(sha256:str)->dict|None:
 api=client();channels=api.channels().list(part='contentDetails',mine=True).execute();playlist=channels['items'][0]['contentDetails']['relatedPlaylists']['uploads'];token=None
 for _ in range(5):
  page=api.playlistItems().list(part='contentDetails',playlistId=playlist,maxResults=50,pageToken=token).execute();ids=[x['contentDetails']['videoId'] for x in page.get('items',[])]
  if ids:
   for row in api.videos().list(part='snippet',id=','.join(ids)).execute().get('items',[]):
    if 'zzdub:'+sha256 in row['snippet'].get('tags',[]):return {'id':row['id'],'url':'https://www.youtube.com/watch?v='+row['id'],'reconciled':True}
  token=page.get('nextPageToken')
  if not token:break
 return None
def execute(episode:Episode,files:dict[str,Path],sha256:str,out:Path,config:dict,publish_at:str|None=None)->dict:
 payload=metadata(episode,sha256,publish_at);save(out/'youtube-payload.json',payload)
 if not config.get('enabled'):return {'status':'preview','payload':'youtube-payload.json','url':None}
 from googleapiclient.http import MediaFileUpload
 api=client();request=api.videos().insert(part='snippet,status',body=payload,media_body=MediaFileUpload(str(files['video']),mimetype='video/mp4',chunksize=8*1024*1024,resumable=True));response=None
 # Do not issue a second insert if acknowledgement is lost. The orchestrator
 # checkpoints publish_pending first and reconciles by immutable content tag.
 while response is None:_,response=request.next_chunk(num_retries=3)
 identity=response['id'];save(out/'youtube-receipt.json',{'id':identity,'url':'https://www.youtube.com/watch?v='+identity,'uploadedAt':time.time(),'postprocessing':'pending'})
 warnings=[]
 for name,action in [('caption',lambda:api.captions().insert(part='snippet',body={'snippet':{'videoId':identity,'language':'es','name':'Español · doblaje automático','isDraft':False}},media_body=MediaFileUpload(str(files['srt']),mimetype='application/octet-stream')).execute()),('thumbnail',lambda:api.thumbnails().set(videoId=identity,media_body=MediaFileUpload(str(files['thumbnail']),mimetype='image/jpeg')).execute())]:
  try:action()
  except Exception as error:warnings.append(name+':'+type(error).__name__)
 try:
  pages=api.playlists().list(part='snippet',mine=True,maxResults=50).execute();name='ZZDub · '+episode.series;playlist=next((x['id'] for x in pages.get('items',[]) if x['snippet']['title']==name),None)
  if not playlist:playlist=api.playlists().insert(part='snippet,status',body={'snippet':{'title':name},'status':{'privacyStatus':'public'}}).execute()['id']
  api.playlistItems().insert(part='snippet',body={'snippet':{'playlistId':playlist,'resourceId':{'kind':'youtube#video','videoId':identity}}}).execute()
 except Exception as error:warnings.append('playlist:'+type(error).__name__)
 receipt={'status':'uploaded','id':identity,'url':'https://www.youtube.com/watch?v='+identity,'warnings':warnings};save(out/'youtube-receipt.json',receipt);return receipt
