package tv.jkanime.web;
import java.io.*;import java.nio.charset.StandardCharsets;import java.security.MessageDigest;import org.json.*;
final class RuntimeOptionAudit {
 static String key(String s)throws Exception{StringBuilder x=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8)))x.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return x.toString();}
 public static void main(String[] args)throws Exception{try(BufferedReader in=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));PrintWriter out=new PrintWriter(new OutputStreamWriter(System.out,StandardCharsets.UTF_8))){String line;while((line=in.readLine())!=null){JSONObject x=new JSONObject(line);String name=x.getString("name"),url=x.getString("url");out.println(new JSONObject().put("key",key(name+"\0"+url)).put("approved",ProviderBackupSample.approved(name,url)).toString());}}}
}
