"""Backup trigger for the existing news job while GitHub schedules are delayed.
Runs under the same serialized data lock as renewal; never creates another collector.
"""
from pathlib import Path
import datetime,json,os,subprocess,sys,time
INTERVAL=300
RETRY=900

def due(folder,now):
    folder=Path(folder)
    try:
        retry=json.loads((folder/'news-watchdog.json').read_bytes())
        if retry.get('retryAt',0)>now:return False
    except (OSError,ValueError,TypeError):pass
    try:
        row=json.loads((folder/'collection-status.json').read_bytes())
        stamp=datetime.datetime.fromisoformat(row['checkedAt'].replace('Z','+00:00')).timestamp()
        return row.get('state')!='complete' or not 0<=now-stamp<INTERVAL
    except (OSError,ValueError,TypeError,KeyError):return True

def check(folder):
    now=time.time();folder=Path(folder)
    if os.environ.get('ZZ_NEWS_WATCHDOG_ENABLED')!='true' or not due(folder,now):return False
    report={'attemptedAt':datetime.datetime.fromtimestamp(now,datetime.timezone.utc).isoformat(),'state':'running','aiCalls':0,'pcRequired':False}
    try:
        subprocess.run([sys.executable,str(Path(__file__).with_name('run.py')),'--collect','--publish'],check=True)
        report.update(state='complete',retryAt=0)
    except Exception as error:
        # Existing workflow logs retain the failure; never store credentials/output in public state.
        report.update(state='failed',error=type(error).__name__,retryAt=time.time()+RETRY)
    (folder/'news-watchdog.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('News watchdog: '+report['state'],flush=True)
    # A failed second batch may still have saved the first. Reload genuine observations either way.
    return True
