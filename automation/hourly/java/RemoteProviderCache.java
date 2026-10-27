package tv.jkanime.web;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.json.*;

/** Signed index plus bounded lazy shard cache. The APK archive remains independent. */
final class RemoteProviderCache implements ProviderBackupStore.Assets {
    interface Fetch {byte[] get(String relative,int limit)throws Exception;}
    private final File folder;private final byte[] key;private final Fetch fetch;
    private JSONObject channel,index,previousIndex;private String revision="",previousRevision="";
    RemoteProviderCache(File folder,byte[] key,Fetch fetch){this.folder=folder;this.key=key.clone();this.fetch=fetch;folder.mkdirs();try{install(read(new File(folder,"channel.json"),65536),false);}catch(Exception ignored){}try{JSONObject old=BackupChannel.verify(read(new File(folder,"previous-channel.json"),65536),key,System.currentTimeMillis(),0);byte[] bytes=read(new File(folder,old.getString("indexSha256")+".index"),2*1024*1024);if(bytes.length==old.getInt("indexBytes")&&ProviderBackupStore.hash(bytes).equals(old.getString("indexSha256"))){previousIndex=new JSONObject(new String(bytes,StandardCharsets.UTF_8)).getJSONObject("series");previousRevision=old.getString("indexSha256");}}catch(Exception ignored){}}
    static byte[] read(File file,int limit)throws Exception{return ProviderBackupStore.read(new FileInputStream(file),limit);}
    static void atomic(File file,byte[] bytes)throws Exception{File temporary=new File(file.getParentFile(),file.getName()+".tmp");try(FileOutputStream out=new FileOutputStream(temporary)){out.write(bytes);out.getFD().sync();}try{Files.move(temporary.toPath(),file.toPath(),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}catch(AtomicMoveNotSupportedException e){Files.move(temporary.toPath(),file.toPath(),StandardCopyOption.REPLACE_EXISTING);}}
    synchronized String revision(){return revision;}
    synchronized int seriesCount(){return index==null?0:index.length();}
    synchronized int episodeCount(){int total=0;if(index!=null)for(Iterator<String> i=index.keys();i.hasNext();)total+=index.optJSONObject(i.next()).optInt("episodes");return total;}
    synchronized boolean refresh()throws Exception{
        byte[] signed=fetch.get("channel.json",65536);JSONObject next=BackupChannel.verify(signed,key,System.currentTimeMillis(),channel==null?0:channel.getLong("sequence"));
        if(channel!=null&&next.getLong("sequence")==channel.getLong("sequence")){if(!next.toString().equals(channel.toString()))throw new IOException("Channel sequence collision");return false;}
        install(signed,true);return true;
    }
    private void install(byte[] signed,boolean download)throws Exception{
        JSONObject next=BackupChannel.verify(signed,key,System.currentTimeMillis(),channel==null?0:channel.getLong("sequence"));String hash=next.getString("indexSha256");File cached=new File(folder,hash+".index");
        byte[] bytes=cached.exists()?read(cached,2*1024*1024):download?fetch.get(next.getString("indexPath"),2*1024*1024):null;
        if(bytes==null||bytes.length!=next.getInt("indexBytes")||!ProviderBackupStore.hash(bytes).equals(hash))throw new IOException("Channel index integrity");
        final byte[] verified=bytes;new ProviderBackupStore(path->{if(!path.equals("provider-backup/index.bin"))throw new IOException("Unexpected index path");return new ByteArrayInputStream(verified);});
        JSONObject parsed=new JSONObject(new String(bytes,StandardCharsets.UTF_8)).getJSONObject("series");
        if(download){atomic(cached,bytes);if(channel!=null&&!revision.equals(hash)){atomic(new File(folder,"previous-channel.json"),read(new File(folder,"channel.json"),65536));previousIndex=index;previousRevision=revision;}atomic(new File(folder,"channel.json"),signed);}
        index=parsed;channel=next;revision=hash;trim();
    }
    @Override public synchronized InputStream open(String path)throws Exception{
        return openFrom(path,index,revision,true);
    }
    synchronized ProviderBackupStore.Assets previousAssets(){if(previousIndex==null)return null;final JSONObject old=previousIndex;final String hash=previousRevision;return path->{synchronized(RemoteProviderCache.this){return openFrom(path,old,hash,false);}};}
    private InputStream openFrom(String path,JSONObject index,String revision,boolean download)throws Exception{
        if(index==null)throw new IOException("Remote archive unavailable");
        if(path.equals("provider-backup/index.bin"))return new FileInputStream(new File(folder,revision+".index"));
        if(!path.matches("provider-backup/series/[a-f0-9]{64}[.]bin"))throw new IOException("Remote archive path");
        String hash=path.substring(path.lastIndexOf('/')+1,path.length()-4);JSONObject entry=null;
        for(Iterator<String> i=index.keys();i.hasNext();){JSONObject candidate=index.getJSONObject(i.next());if(candidate.getString("sha256").equals(hash)){entry=candidate;break;}}
        if(entry==null)throw new IOException("Shard absent from signed index");File cached=new File(folder,hash+".bin");
        byte[] bytes=null;if(cached.exists())try{bytes=read(cached,2*1024*1024);}catch(Exception ignored){}
        if(bytes==null||bytes.length!=entry.getInt("bytes")||!ProviderBackupStore.hash(bytes).equals(hash)){
            if(!download)throw new IOException("Previous shard not cached");
            bytes=fetch.get(entry.getString("path"),2*1024*1024);if(bytes.length!=entry.getInt("bytes")||!ProviderBackupStore.hash(bytes).equals(hash))throw new IOException("Remote shard integrity");atomic(cached,bytes);
        }
        cached.setLastModified(System.currentTimeMillis());trim();return new ByteArrayInputStream(bytes);
    }
    private void trim(){File[] files=folder.listFiles((d,n)->n.matches("[a-f0-9]{64}[.](bin|index)"));if(files==null)return;Arrays.sort(files,Comparator.comparingLong(File::lastModified));long total=0;int count=0;for(File f:files){total+=f.length();count++;}for(File f:files){if(total<=48L*1024*1024&&count<=122)break;if(f.getName().equals(revision+".index")||f.getName().equals(previousRevision+".index"))continue;long size=f.length();if(f.delete()){total-=size;count--;}}}
    static Fetch https(String base){return (relative,limit)->{
        if(!relative.matches("channel[.]json|(?:indexes|series)/[a-f0-9]{64}[.]bin"))throw new IOException("Remote request path");
        URL url=new URL(base+"/"+relative);if(!url.getProtocol().equals("https")||url.getUserInfo()!=null||url.getPort()!=-1)throw new IOException("Remote origin");
        HttpURLConnection c=(HttpURLConnection)url.openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(2500);c.setReadTimeout(3500);c.setUseCaches(false);c.setRequestProperty("Cache-Control","no-cache");c.setRequestProperty("User-Agent","ZZAnime-Data/1");
        try{if(c.getResponseCode()!=200||c.getContentLength()>limit)throw new IOException("Remote response");return ProviderBackupStore.read(c.getInputStream(),limit);}finally{c.disconnect();}
    };}
}
