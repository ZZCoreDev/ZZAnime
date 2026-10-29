package tv.jkanime.web;

import org.jsoup.*;
import org.jsoup.nodes.*;
import java.net.*;
import java.io.IOException;

/** Reads the ordinary public download link. No account, captcha or script execution. */
final class MediafireVideo {
    static boolean page(String raw){try{URI u=new URI(raw.trim());String h=u.getHost();return "https".equals(u.getScheme())&&("mediafire.com".equals(h)||"www.mediafire.com".equals(h))&&u.getUserInfo()==null&&(u.getPort()==-1||u.getPort()==443)&&(u.getPath().startsWith("/file/")||u.getPath().equals("/")&&u.getQuery()!=null&&u.getQuery().matches("[a-zA-Z0-9]+=?"));}catch(Exception e){return false;}}
    static boolean direct(String raw){try{URI u=new URI(raw);String h=u.getHost(),p=u.getPath();return "https".equals(u.getScheme())&&h!=null&&h.matches("download[a-zA-Z0-9-]*[.]mediafire[.]com")&&u.getUserInfo()==null&&(u.getPort()==-1||u.getPort()==443)&&p!=null&&p.toLowerCase(java.util.Locale.ROOT).endsWith(".mp4");}catch(Exception e){return false;}}
    static String parse(Document doc)throws IOException{
        for(Element a:doc.select("a#downloadButton,a.input.popsok,a[aria-label=\"Download file\"]")){
            String encoded=a.attr("data-scrambled-url").trim();if(!encoded.isEmpty())try{String url=new URI(doc.baseUri()).resolve(decode(encoded)).toString();if(direct(url))return url;}catch(Exception ignored){}
            String url=a.absUrl("href").trim();if(direct(url))return url;
        }
        throw new IOException("MediaFire no ofrece un MP4 público compatible o el enlace ha caducado.");
    }
    private static String decode(String value)throws IOException{
        if(value.length()>8192||!value.matches("[A-Za-z0-9+/]+={0,2}"))throw new IOException("Invalid encoded link");String alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();int bits=0,acc=0;
        for(int i=0;i<value.length();i++){char c=value.charAt(i);if(c=='=')break;acc=(acc<<6)|alphabet.indexOf(c);bits+=6;if(bits>=8){bits-=8;out.write((acc>>bits)&255);}}return out.toString("UTF-8");
    }
    static String resolve(String raw)throws Exception{
        String url=raw.trim();for(int hop=0;hop<4;hop++){
            if(Thread.currentThread().isInterrupted())throw new IOException("Cancelled");
            if(!page(url))throw new IOException("Invalid MediaFire URL");
            Connection.Response r=Jsoup.connect(url).userAgent("Mozilla/5.0").timeout(7000).maxBodySize(1024*1024).followRedirects(false).ignoreHttpErrors(true).execute();
            if(r.statusCode()>=300&&r.statusCode()<400){String next=r.header("Location");if(next==null)throw new IOException("Missing redirect");url=new URI(url).resolve(next).toString();continue;}
            if(r.statusCode()!=200)throw new IOException("MediaFire no respondió ("+r.statusCode()+").");return parse(r.parse());
        }throw new IOException("MediaFire redirect limit");
    }
}
