// Intersection of ProviderBackupSample.external/approved, AnimeFlvSource.allowedEmbed,
// and scopedScripts(providerUrl(name)) in automation/hourly/java. Keep parity test green.
export const SUBMIT_POLICY_VERSION='submit-hosts-v1';
export const SUBMIT_HOSTS=Object.freeze({
 mega:Object.freeze(['mega.nz']),
 streamwish:Object.freeze(['streamwish.to','streamwish.com','obeywish.com','hglink.to','hgcloud.to','hanerix.com','audinifer.com']),
 vidhide:Object.freeze(['filelions.top','vidhide.com','vidhidepro.com','vidhidevip.com','callistanise.com']),
 mixdrop:Object.freeze(['mixdrop.ps','mxdrop.click','mxdrop.to','mixdrop.top']),
 mp4upload:Object.freeze(['mp4upload.com']),
 streamtape:Object.freeze(['streamtape.com']),
 // 10/11: Filemoon, as the checked-in Java has accepted since app 170 (4c550168).
 filemoon:Object.freeze(['filemoon.sx','bysekoze.com'])
});
export function submitUrlAllowed(family,raw){
 if(typeof raw!=='string'||raw.length>500||/[\x00-\x20\x7f\\<>"{}|^`]/.test(raw)||/%(?![0-9a-f]{2})/i.test(raw))return false;
 // URL normalizes away an explicit :443, unlike the Java external() contract.
 const authority=/^https:\/\/([^/?#]+)/.exec(raw)?.[1];
 if(!authority||authority!==authority.toLowerCase()||!/^[a-z0-9.-]+$/.test(authority))return false;
 if(authority.length>253||authority.split('.').some(label=>label.length>63||!/^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/.test(label)))return false;
 try{
  const url=new URL(raw),roots=SUBMIT_HOSTS[family];
  return Array.isArray(roots)&&url.protocol==='https:'&&!url.username&&!url.password&&!url.port&&
   roots.some(root=>url.hostname===root||url.hostname.endsWith('.'+root));
 }catch{return false;}
}
