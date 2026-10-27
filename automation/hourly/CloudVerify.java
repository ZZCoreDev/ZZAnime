package tv.jkanime.web;
import java.io.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;import java.util.*;import java.util.zip.GZIPInputStream;import org.json.*;
final class CloudVerify {
 public static void main(String[] args)throws Exception{
  File site=new File(args[0]),key=new File(args[1]),cacheFolder=new File(args[2]);
  RemoteProviderCache.Fetch fetch=args.length>3?RemoteProviderCache.https(args[3]):(p,l)->ProviderBackupStore.read(new FileInputStream(new File(site,p)),l);
  RemoteProviderCache cache=new RemoteProviderCache(cacheFolder,Files.readAllBytes(key.toPath()),fetch);if(!cache.refresh())throw new AssertionError("No signed update");JSONObject expected=new JSONObject(new String(Files.readAllBytes(new File(site,"channel.json").toPath()),StandardCharsets.UTF_8));String expectedRevision=new JSONObject(expected.getString("payload")).getString("indexSha256");if(!cache.revision().equals(expectedRevision))throw new AssertionError("Expected published revision has not reached this edge yet");
  ProviderBackupStore store=new ProviderBackupStore(cache);JSONObject index=new JSONObject(new String(ProviderBackupStore.read(cache.open("provider-backup/index.bin"),2097152),StandardCharsets.UTF_8)).getJSONObject("series");int episodes=0,options=0;
  for(Iterator<String> it=index.keys();it.hasNext();){JSONObject entry=index.getJSONObject(it.next());byte[] packed=ProviderBackupStore.read(cache.open("provider-backup/"+entry.getString("path")),2097152);JSONObject row=new JSONObject(new String(ProviderBackupStore.read(new GZIPInputStream(new ByteArrayInputStream(packed)),2097152),StandardCharsets.UTF_8));String parent=row.getString("series");if(!store.prepare(parent))throw new AssertionError("Real app rejected shard");
   JSONObject snapshot=store.snapshot(parent,ProviderBackupSample::approved);if(snapshot==null)throw new AssertionError("No usable real app chapter");
   for(int i=0;i<row.getJSONArray("episodes").length();i++){String url=row.getJSONArray("episodes").getJSONObject(i).getString("url");int n=store.options(url,ProviderBackupSample::approved).length();if(n<1)throw new AssertionError("No approved option");episodes++;options+=n;}
  }
  if(index.length()<1||episodes<1)throw new AssertionError("Empty update");System.out.println(new JSONObject().put("realAppAccepted",true).put("series",index.length()).put("episodes",episodes).put("options",options).put("physicalAndroidPlayback",false));
 }
}
