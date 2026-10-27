package tv.jkanime.web;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;
import java.util.function.BiPredicate;
import java.util.zip.GZIPInputStream;

/** Verified per-series archive. Disk I/O is explicit in prepare(), called off the UI thread. */
final class ProviderBackupStore {
 interface Assets {InputStream open(String path)throws Exception;}
 private static final int LIMIT=2*1024*1024;
 private final Assets assets;private final JSONObject index;
 private final LinkedHashMap<String,JSONObject> cache=new LinkedHashMap<>(8,.75f,true);
 private final HashSet<String> failed=new HashSet<>();
 private String failureReason="";
 synchronized String failureReason(){return failureReason;}
 ProviderBackupStore(Assets assets)throws Exception{
  this.assets=assets;JSONObject root=new JSONObject(new String(read(assets.open("provider-backup/index.bin"),LIMIT),StandardCharsets.UTF_8));
  if(root.getInt("schema")!=1||root.optBoolean("playbackVerified",true))throw new IOException("Archive schema");
  index=root.getJSONObject("series");if(index.length()>5053)throw new IOException("Archive index limit");
  for(Iterator<String> i=index.keys();i.hasNext();){String key=i.next();JSONObject x=index.getJSONObject(key);String hash=x.getString("sha256");if(!key.matches("[a-f0-9]{64}")||!hash.matches("[a-f0-9]{64}")||!x.getString("path").equals("series/"+hash+".bin")||x.getInt("bytes")<1||x.getInt("bytes")>LIMIT||x.getInt("expandedBytes")<1||x.getInt("expandedBytes")>LIMIT||x.getInt("episodes")<1)throw new IOException("Archive index identity/limit");}
 }
 static byte[] read(InputStream source,int limit)throws Exception{try(InputStream in=source;ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(out.size()+n>limit)throw new IOException("Archive size limit");out.write(b,0,n);}return out.toByteArray();}}
 static String hash(byte[] bytes)throws Exception{StringBuilder s=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(bytes))s.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return s.toString();}
 synchronized boolean prepare(String parent){
  if(!parent.equals(ProviderBackupSample.series(parent)))return false;
  if(cache.containsKey(parent))return true;if(failed.contains(parent))return false;
  try{
   JSONObject entry=index.optJSONObject(hash(parent.getBytes(StandardCharsets.UTF_8)));if(entry==null)return false;
   byte[] packed=read(assets.open("provider-backup/"+entry.getString("path")),LIMIT);if(packed.length!=entry.getInt("bytes")||!hash(packed).equals(entry.getString("sha256")))throw new IOException("Archive hash");
   byte[] bytes=read(new GZIPInputStream(new ByteArrayInputStream(packed)),LIMIT);if(bytes.length!=entry.getInt("expandedBytes"))throw new IOException("Archive expanded length");
   JSONObject row=new JSONObject(new String(bytes,StandardCharsets.UTF_8));if(row.getInt("schema")!=1||!parent.equals(row.getString("series"))||row.optBoolean("playbackVerified",true))throw new IOException("Archive series");
   JSONArray listed=row.getJSONArray("listedEpisodes"),eps=row.getJSONArray("episodes");if(listed.length()>100000||eps.length()!=entry.getInt("episodes"))throw new IOException("Archive counts");
   HashSet<String> observed=new HashSet<>(),seen=new HashSet<>();for(int i=0;i<listed.length();i++){String u=listed.getString(i);if(number(u,parent)<1||!observed.add(u))throw new IOException("Observed chapter identity");}
   for(int i=0;i<eps.length();i++){JSONObject ep=eps.getJSONObject(i);String u=ep.getString("url");if(number(u,parent)<1||!observed.contains(u)||!seen.add(u)||ep.optBoolean("playbackVerified",true))throw new IOException("Archive chapter identity");
    long time=Instant.parse(ep.getString("observedAt")).toEpochMilli();if(time>System.currentTimeMillis()+300000)throw new IOException("Future observation");JSONArray options=ep.getJSONArray("options");if(options.length()<1||options.length()>24)throw new IOException("Archive options limit");
    for(int k=0;k<options.length();k++){JSONObject p=options.getJSONObject(k);String name=p.getString("name");if(name.length()>70||!ProviderPlaybackPolicy.family(name).equals(p.getString("family"))||!ProviderBackupSample.approved(name,p.getString("url")))throw new IOException("Archive provider policy");}
   }
   cache.put(parent,row);while(cache.size()>4)cache.remove(cache.keySet().iterator().next());return true;
  }catch(Exception e){String message=e.getMessage();failureReason=message!=null&&(message.startsWith("Archive ")||message.startsWith("Observed ")||message.startsWith("Future "))?message:e.getClass().getSimpleName();failed.add(parent);return false;}
 }
 static int number(String url,String parent){try{if(!url.startsWith(parent))return 0;String tail=url.substring(parent.length());if(!tail.matches("[1-9][0-9]*/"))return 0;int n=Integer.parseInt(tail.substring(0,tail.length()-1));return n<=100000?n:0;}catch(Exception e){return 0;}}
 private static boolean fresh(JSONObject ep){try{long age=System.currentTimeMillis()-Instant.parse(ep.getString("observedAt")).toEpochMilli();return age>=0&&age<=7*86400000L;}catch(Exception e){return false;}}
 synchronized JSONArray options(String url,BiPredicate<String,String> approved){JSONArray result=new JSONArray();try{JSONObject row=cache.get(url.replaceAll("/[0-9]+/$","/"));if(row==null)return result;JSONArray eps=row.getJSONArray("episodes");for(int i=0;i<eps.length();i++){JSONObject ep=eps.getJSONObject(i);if(!url.equals(ep.getString("url"))||!fresh(ep))continue;JSONArray options=ep.getJSONArray("options");for(int j=0;j<options.length();j++){JSONObject x=options.getJSONObject(j);if(approved.test(x.getString("name"),x.getString("url")))result.put(new JSONObject(x.toString()));}}}catch(Exception ignored){}return result;}
 synchronized JSONObject snapshot(String parent,BiPredicate<String,String> approved){try{
  JSONObject row=cache.get(parent);if(row==null)return null;JSONArray eps=row.getJSONArray("episodes"),out=new JSONArray();int maximum=0;long oldest=Long.MAX_VALUE;
  ArrayList<JSONObject> sorted=new ArrayList<>();for(int i=0;i<eps.length();i++)sorted.add(eps.getJSONObject(i));Collections.sort(sorted,(a,b)->Integer.compare(number(a.optString("url"),parent),number(b.optString("url"),parent)));
  for(JSONObject ep:sorted){String u=ep.getString("url");if(!fresh(ep))continue;JSONArray opts=ep.getJSONArray("options");boolean available=false;for(int k=0;k<opts.length();k++){JSONObject p=opts.getJSONObject(k);if(approved.test(p.getString("name"),p.getString("url"))){available=true;break;}}if(!available)continue;int n=number(u,parent);maximum=Math.max(maximum,n);oldest=Math.min(oldest,Instant.parse(ep.getString("observedAt")).toEpochMilli());out.put(new JSONObject().put("url",u).put("number",n).put("title","Episodio "+n).put("image",""));}
  if(out.length()==0)return null;return new JSONObject().put("episodes",out).put("episodeTotal",maximum).put("savedAt",oldest).put("providerBackupArchive",true).put("archivedCount",out.length()).put("observedCount",row.getJSONArray("listedEpisodes").length());
 }catch(Exception e){return null;}}
}
