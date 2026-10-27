package tv.jkanime.web;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.spec.X509EncodedKeySpec;
import java.time.Instant;
import org.json.JSONObject;

/** Authenticates data-only updates. Never downloads code, permissions or provider rules. */
final class BackupChannel {
    static JSONObject verify(byte[] envelope,byte[] key,long now,long minimum)throws Exception{
        if(envelope.length>65536)throw new IOException("Channel size");
        JSONObject wrapper=new JSONObject(new String(envelope,StandardCharsets.UTF_8));
        String payload=wrapper.getString("payload"),hex=wrapper.getString("signature");
        if(!hex.matches("[a-f0-9]{512}"))throw new IOException("Channel signature encoding");
        byte[] signature=new byte[256];for(int i=0;i<signature.length;i++)signature[i]=(byte)Integer.parseInt(hex.substring(i*2,i*2+2),16);
        Signature verifier=Signature.getInstance("SHA256withRSA");verifier.initVerify(KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(key)));verifier.update(payload.getBytes(StandardCharsets.UTF_8));
        if(!verifier.verify(signature))throw new IOException("Channel signature");
        JSONObject x=new JSONObject(payload);String hash=x.getString("indexSha256");long generated=Instant.parse(x.getString("createdAt")).toEpochMilli(),version=x.getLong("sequence");
        if(x.getInt("schema")!=1||version<minimum||version<1||generated>now+300000||now-generated>7*86400000L||!hash.matches("[a-f0-9]{64}")||!x.getString("indexPath").equals("indexes/"+hash+".bin")||x.getInt("indexBytes")<1||x.getInt("indexBytes")>2*1024*1024||!x.optString("mode").matches("daily-new|full"))throw new IOException("Channel metadata");
        return x;
    }
}
