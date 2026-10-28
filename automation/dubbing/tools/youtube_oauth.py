"""Interactive account-owner setup; sends the refresh token straight to GitHub Secrets."""
import getpass,subprocess
from google_auth_oauthlib.flow import InstalledAppFlow
def main()->None:
 client_id=input('Desktop OAuth client ID: ').strip();client_secret=getpass.getpass('Desktop OAuth client secret (hidden): ').strip();config={'installed':{'client_id':client_id,'client_secret':client_secret,'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token','redirect_uris':['http://localhost']}}
 flow=InstalledAppFlow.from_client_config(config,scopes=['https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.force-ssl']);credentials=flow.run_local_server(port=0,access_type='offline',prompt='consent')
 subprocess.run(['gh','secret','set','YOUTUBE_OAUTH_JSON','--repo','ZZCoreDev/ZZAnime'],input=credentials.to_json(),text=True,check=True,capture_output=True);print('YOUTUBE_OAUTH_JSON stored in GitHub Secrets; token not printed or saved as a local file.')
if __name__=='__main__':main()
