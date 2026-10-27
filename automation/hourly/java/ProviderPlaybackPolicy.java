package tv.jkanime.web;
import java.util.Locale;
/** Known-provider recovery rules; never grants scripts to arbitrary domains. */
final class ProviderPlaybackPolicy {
    static boolean megaName(String name){return name!=null&&name.trim().toLowerCase(Locale.ROOT).matches("mega(?:[\\s0-9:()_-].*)?");}
    static String family(String name){if(name==null)return "";String n=name.trim().toLowerCase(Locale.ROOT);if(n.matches("streamtape?(?:[\\s0-9:()_-].*)?"))return "streamtape";for(String f:new String[]{"desu","magi","mega","streamwish","vidhide","mixdrop","mp4upload"})if(n.matches(f+"(?:[\\s0-9:()_-].*)?"))return f;return "";}
    static boolean allowedJk(String name){return !family(name).isEmpty();}
    static String providerUrl(String name){switch(family(name)){case "mega":return "https://mega.nz/";case "streamwish":return "https://streamwish.com/";case "vidhide":return "https://vidhide.com/";case "mixdrop":return "https://mxdrop.click/";case "mp4upload":return "https://mp4upload.com/";case "streamtape":return "https://streamtape.com/";default:return "";}}
    static int startupDelay(String name,boolean alternative){return megaName(name)?25000:family(name).equals("streamtape")?30000:alternative?15000:10000;}
    static boolean appGestures(boolean started,boolean nativeVideo,boolean casting){return started||nativeVideo||casting;}
    private static boolean under(String host,String[] domains){for(String d:domains)if(host.equals(d)||host.endsWith("."+d))return true;return false;}
    static boolean scriptPermitted(String host,String path,String destination,String[] base,String[] selected){
        boolean executable="script".equalsIgnoreCase(destination)||"worker".equalsIgnoreCase(destination)||path.endsWith(".js")||path.endsWith(".mjs");
        return !executable||under(host,base)||under(host,selected);
    }
    static boolean inside(float x,float y,int left,int top,int width,int height){return width>0&&height>0&&x>=left&&y>=top&&x<left+width&&y<top+height;}
}
