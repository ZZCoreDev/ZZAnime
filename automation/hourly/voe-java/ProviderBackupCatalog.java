package tv.jkanime.web;

import java.util.*;
import java.util.function.BiPredicate;
import org.json.*;

/** Combines partial daily additions with the bundled archive without dropping older chapters. */
final class ProviderBackupCatalog {
    private final ProviderBackupStore bundled;private final RemoteProviderCache updates;
    private ProviderBackupStore remote,previous;private String revision="";private RemoteProviderCache additions;private ProviderBackupStore additional;private String additionalRevision="";
    ProviderBackupCatalog(ProviderBackupStore.Assets assets,RemoteProviderCache updates)throws Exception{bundled=new ProviderBackupStore(assets);this.updates=updates;}
    ProviderBackupCatalog(ProviderBackupStore.Assets assets,RemoteProviderCache updates,RemoteProviderCache additions)throws Exception{this(assets,updates);this.additions=additions;}
    synchronized boolean prepare(String series){
        boolean ready=bundled.prepare(series);
        if(updates!=null)try{String next=updates.revision();if(!next.equals(revision)){remote=next.isEmpty()?null:new ProviderBackupStore(updates);ProviderBackupStore.Assets old=updates.previousAssets();previous=old==null?null:new ProviderBackupStore(old);revision=next;}if(previous!=null)ready=previous.prepare(series)||ready;if(remote!=null){if(remote.prepare(series))ready=true;else{remote=null;revision="";}}}catch(Exception ignored){remote=null;revision="";}
        if(additions!=null)try{String next=additions.revision();if(!next.equals(additionalRevision)){additional=next.isEmpty()?null:new ProviderBackupStore(additions);additionalRevision=next;}if(additional!=null)ready=additional.prepare(series)||ready;}catch(Exception ignored){additional=null;additionalRevision="";}
        return ready;
    }
    synchronized JSONArray options(String url,BiPredicate<String,String> allowed){
        JSONArray a=bundled.options(url,allowed),b=remote==null?new JSONArray():remote.options(url,allowed),c=previous==null?new JSONArray():previous.options(url,allowed);JSONArray out=new JSONArray();HashSet<String> seen=new HashSet<>();
        for(JSONArray source:new JSONArray[]{b,c,a,additional==null?new JSONArray():additional.options(url,allowed)})for(int i=0;i<source.length();i++){JSONObject item=source.optJSONObject(i);if(item!=null&&seen.add(item.optString("family")+"\0"+item.optString("url")))out.put(item);}return out;
    }
    synchronized JSONObject snapshot(String series,BiPredicate<String,String> allowed){
        JSONObject a=merge(bundled.snapshot(series,allowed),previous==null?null:previous.snapshot(series,allowed)),b=remote==null?null:remote.snapshot(series,allowed);return merge(merge(a,b),additional==null?null:additional.snapshot(series,allowed));
    }
    synchronized JSONArray downloads(String url){JSONArray out=new JSONArray();HashSet<String> seen=new HashSet<>();for(ProviderBackupStore store:new ProviderBackupStore[]{remote,previous,bundled,additional})if(store!=null){JSONArray rows=store.downloads(url);for(int i=0;i<rows.length();i++){JSONObject item=rows.optJSONObject(i);if(item!=null&&seen.add(item.optString("url")))out.put(item);}}return out;}
    synchronized JSONObject detail(String series,BiPredicate<String,String> allowed){JSONObject result=null;for(ProviderBackupStore store:new ProviderBackupStore[]{bundled,previous,remote,additional})if(store!=null)result=merge(result,store.listing(series));return merge(result,snapshot(series,allowed));}
    private JSONObject merge(JSONObject a,JSONObject b){if(a==null)return b;if(b==null)return a;
        try{TreeMap<Integer,JSONObject> rows=new TreeMap<>();for(JSONObject source:new JSONObject[]{a,b}){JSONArray eps=source.getJSONArray("episodes");for(int i=0;i<eps.length();i++){JSONObject ep=eps.getJSONObject(i);rows.put(ep.getInt("number"),ep);}}
            JSONArray eps=new JSONArray();for(JSONObject ep:rows.values())eps.put(ep);return new JSONObject(a.toString()).put("episodes",eps).put("episodeTotal",rows.lastKey()).put("archivedCount",eps.length()).put("observedCount",Math.max(eps.length(),Math.max(a.optInt("observedCount"),b.optInt("observedCount")))).put("savedAt",Math.max(a.optLong("savedAt"),b.optLong("savedAt")));
        }catch(Exception ignored){return a;}
    }
}
