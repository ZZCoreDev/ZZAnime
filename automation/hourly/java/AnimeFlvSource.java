package tv.jkanime.web;

import org.jsoup.*;
import org.jsoup.nodes.*;
import org.json.*;
import java.net.*;
import java.util.*;
import java.text.Normalizer;
import java.io.IOException;

/** Public page adapter. Canonical ZZAnime library identifiers never change. */
final class AnimeFlvSource {
    static final String BASE="https://vww.animeflv.one/";
    static final class Match {final String title,url;Match(String t,String u){title=t;url=u;}}
    static final class Mirror {final String name,url;String unavailable="",page="",directUrl="";Mirror(String n,String u){name=n;url=u;}}
    static final class Result {int source=3;String page="";boolean next;final ArrayList<Mirror> mirrors=new ArrayList<>();final ArrayList<Match> choices=new ArrayList<>();}
    private final Map<String,Match> confirmed=new HashMap<>();
    static String normal(String value){return Normalizer.normalize(value.replaceFirst("(?i)^\\s*Ver\\s+", "").replaceFirst("(?i)\\s+Sub\\s+espa[nñ]ol(?:\\s+latino)?\\s+Online\\s*$", ""),Normalizer.Form.NFD).replaceAll("\\p{M}","").toLowerCase(Locale.ROOT).replaceAll("\\(tv\\)","").replaceAll("[^a-z0-9]","");}
    static boolean allowedPage(String url){try{URI u=new URI(url);String h=u.getHost();return "https".equals(u.getScheme())&&u.getUserInfo()==null&&(h!=null&&(h.equals("animeflv.one")||h.endsWith(".animeflv.one")))&&(u.getPort()==-1||u.getPort()==443);}catch(Exception e){return false;}}
    static boolean allowedEmbed(String url){try{URI u=new URI(url);if(MediafireVideo.page(url))return true;if(!"https".equals(u.getScheme())||u.getUserInfo()!=null||(u.getPort()!=-1&&u.getPort()!=443))return false;String h=u.getHost();if(h==null)return false;for(String root:EMBED_HOSTS)if(h.equals(root)||h.endsWith("."+root))return true;}catch(Exception ignored){}return false;}
    static final String[] EMBED_HOSTS={"ok.ru","odnoklassniki.ru","yourupload.com","embedsb.com","embedsito.com","hqq.tv","mp4upload.com","streamtape.com","filemoon.sx","vidhide.com","vidhidepro.com","hglink.to","streamwish.com","voe.sx","dooodster.com","playmogo.com","luluvdo.com","lulustream.com","streamwish.to","bysesukior.com","filelions.top","uqload.is","uqload.vc","mixdrop.ps","mxdrop.click","mega.nz","my.mail.ru","v.tioanime.com","vgfplay.com","doodstream.com","dood.watch","dsvplay.com","uqload.io","uqload.cx","obeywish.com","luluvid.com","mxdrop.to","mediafire.com","hgcloud.to","hanerix.com","audinifer.com","vidhidevip.com","callistanise.com","mixdrop.top"};
    private static final String[][] SCOPED_FAMILIES={{"dooodster.com","playmogo.com","doodstream.com","dood.watch","dsvplay.com"},{"luluvdo.com","lulustream.com","luluvid.com"},{"streamwish.to","streamwish.com","obeywish.com","hglink.to","hgcloud.to","hanerix.com","audinifer.com"},{"bysesukior.com"},{"filelions.top","vidhide.com","vidhidepro.com","vidhidevip.com","callistanise.com"},{"uqload.is","uqload.vc","uqload.io","uqload.cx"},{"mixdrop.ps","mxdrop.click","mxdrop.to","mixdrop.top"},{"mega.nz","static.mega.co.nz"},{"my.mail.ru"},{"yourupload.com"},{"v.tioanime.com"},{"vgfplay.com"},{"mp4upload.com"},{"streamtape.com"}};
    private static boolean under(String host,String root){return host!=null&&(host.equals(root)||host.endsWith("."+root));}
    static String[] scopedScripts(String selected){for(String[] family:SCOPED_FAMILIES)for(String root:family)if(under(selected,root))return family.clone();return new String[0];}
    static boolean sameProvider(String a,String b){for(String root:EMBED_HOSTS)if(under(a,root)&&under(b,root))return true;for(String root:scopedScripts(b))if(under(a,root))return true;return false;}
    private static int priority(Mirror m){String name=m.name.toLowerCase(Locale.ROOT);if(name.contains("dood"))return 0;if(name.contains("mega"))return 1;if(name.contains("mp4upload"))return 2;if(name.contains("uqload"))return 3;if(name.contains("mediafire"))return 4;if(name.contains("streamtape"))return 5;if(name.contains("streamwish")||name.startsWith("sw"))return 6;if(name.contains("lulu"))return 7;if(name.contains("voe"))return 8;if(name.contains("filemoon")||name.contains("byse")||name.contains("vidhide")||name.contains("mixdrop")||name.contains("maru"))return 10;return 9;}
    static void order(List<Mirror> mirrors){Collections.sort(mirrors,(a,b)->Integer.compare(priority(a),priority(b)));}
    private Document get(String url)throws Exception{
        for(int redirects=0;redirects<4;redirects++){
            if(Thread.currentThread().isInterrupted())throw new IOException("Cancelled");if(!allowedPage(url))throw new IOException("Invalid source URL");
            Connection.Response response=Jsoup.connect(url).userAgent("Mozilla/5.0").timeout(8000).maxBodySize(2*1024*1024).followRedirects(false).ignoreHttpErrors(true).execute();
            if(response.statusCode()>=300&&response.statusCode()<400){url=new URI(url).resolve(response.header("Location")).toString();continue;}
            if(response.statusCode()!=200)throw new IOException("Source HTTP "+response.statusCode());Document doc=response.parse();if(doc.title().contains("Just a moment")||doc.select("[id*=challenge]").size()>0)throw new IOException("Source verification required");return doc;
        }throw new IOException("Redirect limit");
    }
    Result resolve(String canonical,String title,int episode,Match selected)throws Exception{
        if(episode<1||episode>100000)throw new IOException("Invalid episode");Match saved=selected!=null?selected:confirmed.get(canonical);if(saved!=null){Result result=episode(saved,episode);confirmed.put(canonical,saved);return result;}
        String slug=new URI(canonical).getPath().replaceAll("^/+|/+$","");String expected=normal(title);
        if(slug.matches("[a-zA-Z0-9_-]+")){try{Document direct=get(BASE+"anime/"+slug);Element h=direct.selectFirst("h1");if(h!=null&&normal(h.text()).equals(expected)){Match match=new Match(h.text(),BASE+"anime/"+slug);Result result=episode(match,episode);confirmed.put(canonical,match);return result;}}catch(IOException ignored){}}
        Document search=get(BASE+"animes?buscar="+URLEncoder.encode(title.substring(0,Math.min(100,title.length())),"UTF-8"));LinkedHashMap<String,Match> matches=new LinkedHashMap<>();
        for(Element a:search.select("a[href]")){String url=a.absUrl("href");if(!allowedPage(url)||!new URI(url).getPath().matches("/anime/[a-zA-Z0-9_-]+/?"))continue;String label=a.attr("title");if(label.isEmpty())label=a.text();if(label.trim().isEmpty())continue;matches.putIfAbsent(url,new Match(label,url));}
        ArrayList<Match> exact=new ArrayList<>();for(Match match:matches.values())if(normal(match.title).equals(expected))exact.add(match);
        if(exact.size()==1){Result result=episode(exact.get(0),episode);confirmed.put(canonical,exact.get(0));return result;}
        Result result=new Result();for(Match match:matches.values()){result.choices.add(match);if(result.choices.size()==8)break;}if(result.choices.isEmpty())throw new IOException("No matching series");return result;
    }
    private Result episode(Match match,int number)throws Exception{
        Document detail=get(match.url);Element slugElement=detail.selectFirst("[data-sl]"),heading=detail.selectFirst("h1");if(slugElement==null||heading==null)throw new IOException("Invalid series page");String slug=slugElement.attr("data-sl");if(!slug.matches("[a-zA-Z0-9_-]+"))throw new IOException("Invalid slug");
        JSONArray episodes=null;java.util.regex.Pattern pattern=java.util.regex.Pattern.compile("(?:var|let|const)\\s+eps\\s*=\\s*");for(Element script:detail.select("script")){java.util.regex.Matcher matcher=pattern.matcher(script.data());if(matcher.find()){Object value=new JSONTokener(script.data().substring(matcher.end())).nextValue();if(value instanceof JSONArray)episodes=(JSONArray)value;break;}}
        if(episodes==null)throw new IOException("Episode list unavailable");String suffix=null;boolean next=false;for(int i=0;i<episodes.length();i++){JSONArray row=episodes.optJSONArray(i);if(row==null)continue;if(row.optInt(0)==number){String code=row.optString(2,"");if(!code.matches("[a-zA-Z0-9_-]*"))throw new IOException("Invalid episode code");suffix=code.isEmpty()?"":"-"+code;}if(row.optInt(0)==number+1)next=true;}
        if(suffix==null)throw new IOException("Episode not available");String page=BASE+"ver/"+slug+"-"+number+suffix;Document doc=get(page);Element player=doc.selectFirst(".ply"),options=doc.selectFirst(".opt[data-encrypt]"),h=doc.selectFirst("h1");
        if(player==null||options==null||h==null||(!normal(h.text()).startsWith(normal(heading.text()))||!normal(h.text()).endsWith("episodio"+number)))throw new IOException("Episode verification failed");String key=options.attr("data-encrypt");if(!key.matches("[a-fA-F0-9]{2,256}"))throw new IOException("Invalid options key");
        Connection.Response response=Jsoup.connect(BASE+"flv").userAgent("Mozilla/5.0").referrer(page).header("Origin",BASE.substring(0,BASE.length()-1)).header("X-Requested-With","XMLHttpRequest").timeout(8000).maxBodySize(256*1024).followRedirects(false).data("acc","opt","i",key).method(Connection.Method.POST).execute();
        Result result=new Result();result.page=page;result.next=next;Document optionsDoc=Jsoup.parseBodyFragment(response.body(),BASE);HashSet<String> seen=new HashSet<>();
        for(Element li:optionsDoc.select("li[encrypt]")){String value=li.attr("encrypt");if(!value.matches("[a-fA-F0-9]{2,8000}")||value.length()%2!=0)continue;byte[] bytes=new byte[value.length()/2];for(int i=0;i<bytes.length;i++)bytes[i]=(byte)Integer.parseInt(value.substring(i*2,i*2+2),16);String url=new String(bytes,java.nio.charset.StandardCharsets.UTF_8);if(!allowedEmbed(url)||!seen.add(url))continue;Element serverLabel=li.selectFirst("span");String label=serverLabel!=null?serverLabel.text():li.text();result.mirrors.add(new Mirror(label.length()>70?label.substring(0,70):label,url));}
        if(result.mirrors.isEmpty())throw new IOException("No supported HTTPS mirrors");Collections.sort(result.mirrors,(a,b)->Integer.compare(priority(a),priority(b)));return result;
    }
    static String wrapper(Mirror mirror){if(MediafireVideo.direct(mirror.directUrl))return "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>html,body{margin:0;width:100%;height:100%;background:#000}video{width:100%;height:100%;object-fit:contain}</style></head><body><video controls autoplay playsinline preload='metadata' src='"+mirror.directUrl.replace("&","&amp;").replace("'","&#39;").replace("<","&lt;").replace(">","&gt;")+"'></video></body></html>";return "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='referrer' content='strict-origin-when-cross-origin'><style>html,body{margin:0;width:100%;height:100%;background:#000;overflow:hidden}iframe{position:fixed;inset:0;border:0;width:100%;height:100%}</style></head><body><iframe sandbox='allow-scripts allow-same-origin allow-presentation allow-forms allow-downloads' src='"+mirror.url.replace("&","&amp;").replace("'","&#39;").replace("<","&lt;").replace(">","&gt;")+"' allow='autoplay; fullscreen; picture-in-picture' allowfullscreen tabindex='0'></iframe></body></html>";}
}
