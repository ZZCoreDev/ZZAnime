from __future__ import annotations
import json,os,smtplib,ssl,urllib.request
from email.message import EmailMessage
from pathlib import Path
from .core import save
def execute(summary:dict,out:Path)->dict:
 save(out/'summary.json',summary);delivered=[];failures=[];text=json.dumps(summary,ensure_ascii=False,indent=2)
 if os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'):
  try:
   url='https://api.telegram.org/bot'+os.environ['TELEGRAM_BOT_TOKEN']+'/sendMessage';req=urllib.request.Request(url,data=json.dumps({'chat_id':os.environ['TELEGRAM_CHAT_ID'],'text':text[:3800]}).encode(),headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=20) as response:json.load(response)
   delivered.append('telegram')
  except Exception as error:failures.append('telegram:'+type(error).__name__)
 if all(os.getenv(x) for x in ['SMTP_HOST','SMTP_USER','SMTP_PASSWORD','NOTIFY_EMAIL']):
  try:
   message=EmailMessage();message['Subject']='ZZDub · resultado automático';message['From']=os.environ['SMTP_USER'];message['To']=os.environ['NOTIFY_EMAIL'];message.set_content(text)
   with smtplib.SMTP_SSL(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','465')),context=ssl.create_default_context(),timeout=20) as client:client.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']);client.send_message(message)
   delivered.append('email')
  except Exception as error:failures.append('email:'+type(error).__name__)
 result={'delivered':delivered,'failures':failures,'local_report':str(out/'summary.json')};save(out/'notification.json',result);return result
