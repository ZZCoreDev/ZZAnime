package tv.jkanime.web;
import org.json.*;
import java.io.*;
import java.net.URI;
import java.time.Instant;
import java.util.*;
import java.util.function.BiPredicate;
import java.util.zip.GZIPInputStream;

/** Small local proof of the archive integration. No network, downloads, credentials or domain learning. */
final class ProviderBackupSample {
    private static volatile JSONObject data=new JSONObject();
    static boolean approved(String name,String url){
        String selected=ProviderPlaybackPolicy.providerUrl(name);if(selected.isEmpty()||!external(url)||!AnimeFlvSource.allowedEmbed(url))return false;
        try{String host=new URI(url).getHost(),selectedHost=new URI(selected).getHost();for(String root:AnimeFlvSource.scopedScripts(selectedHost))if(host.equals(root)||host.endsWith("."+root))return true;}catch(Exception ignored){}return false;
    }
    static String series(String raw){try{URI u=new URI(raw);if(!"https".equals(u.getScheme())||!"jkanime.net".equals(u.getHost())||u.getUserInfo()!=null||u.getPort()!=-1||u.getQuery()!=null||u.getFragment()!=null||!u.getPath().matches("/[a-zA-Z0-9_-]+/"))return "";return raw;}catch(Exception e){return "";}}
    static boolean episode(String raw,String parent,int number){return number>0&&number<=100000&&raw.equals(parent+number+"/");}
    static boolean external(String raw){try{URI u=new URI(raw);return "https".equals(u.getScheme())&&u.getHost()!=null&&!u.getHost().equals("jkanime.net")&&!u.getHost().equals("www.jkanime.net")&&u.getUserInfo()==null&&u.getPort()==-1&&raw.length()<=8192;}catch(Exception e){return false;}}
    static void load(InputStream input)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(InputStream in=new GZIPInputStream(input)){byte[] b=new byte[4096];int n;while((n=in.read(b))!=-1){if(bytes.size()+n>262144)throw new IOException("Sample limit");bytes.write(b,0,n);}}
        JSONObject root=new JSONObject(bytes.toString("UTF-8")),next=new JSONObject();if(root.getInt("schema")!=1||!root.optBoolean("sample"))throw new IOException("Sample schema");JSONArray rows=root.getJSONArray("series");if(rows.length()>2)throw new IOException("Only the two-series proof is enabled");
        for(int i=0;i<rows.length();i++){JSONObject row=rows.getJSONObject(i);String parent=series(row.getString("url"));if(parent.isEmpty()||next.has(parent))throw new IOException("Series identity");long date=Instant.parse(row.getString("observedAt")).toEpochMilli();if(date>System.currentTimeMillis()+300000)throw new IOException("Future observation");JSONArray episodes=row.getJSONArray("episodes");if(episodes.length()>4)throw new IOException("Sample episode limit");HashSet<String> seen=new HashSet<>();
            for(int j=0;j<episodes.length();j++){JSONObject ep=episodes.getJSONObject(j);if(!episode(ep.getString("url"),parent,ep.getInt("number"))||!seen.add(ep.getString("url")))throw new IOException("Episode identity");JSONArray options=ep.getJSONArray("options");if(options.length()<1||options.length()>24)throw new IOException("Option limit");for(int k=0;k<options.length();k++){JSONObject option=options.getJSONObject(k);if(option.optString("name").length()>70||!external(option.getString("url")))throw new IOException("Invalid external option");}}
            next.put(parent,row);
        }data=next;
    }
    static JSONObject find(String parent){JSONObject row=data.optJSONObject(parent);if(row==null)return null;try{long age=System.currentTimeMillis()-Instant.parse(row.getString("observedAt")).toEpochMilli();return age>=0&&age<=7*86400000L?row:null;}catch(Exception e){return null;}}
    static JSONArray options(String url,BiPredicate<String,String> approved){try{String parent=url.replaceAll("/[0-9]+/$","/");JSONObject row=find(parent);if(row==null)return new JSONArray();JSONArray eps=row.getJSONArray("episodes"),result=new JSONArray();for(int i=0;i<eps.length();i++){JSONObject ep=eps.getJSONObject(i);if(!url.equals(ep.optString("url")))continue;JSONArray options=ep.getJSONArray("options");for(int j=0;j<options.length();j++){JSONObject p=options.getJSONObject(j);if(approved.test(p.getString("name"),p.getString("url")))result.put(new JSONObject(p.toString()));}}return result;}catch(Exception e){return new JSONArray();}}
    static JSONObject snapshot(String parent,BiPredicate<String,String> approved){try{JSONObject row=find(parent);if(row==null)return null;JSONArray eps=row.getJSONArray("episodes"),result=new JSONArray();for(int i=0;i<eps.length();i++){JSONObject ep=eps.getJSONObject(i);if(options(ep.getString("url"),approved).length()>0)result.put(new JSONObject().put("url",ep.getString("url")).put("title","Episodio "+ep.getInt("number")).put("number",ep.getInt("number")).put("image",""));}if(result.length()==0)return null;return new JSONObject().put("title",row.getString("title")).put("episodes",result).put("episodeTotal",result.length()).put("savedAt",Instant.parse(row.getString("observedAt")).toEpochMilli()).put("providerBackupSample",true);}catch(Exception e){return null;}}
}
