'use strict';
function rateBlocked(status,text=''){return status===429||/demasiadas\s+peticiones|(?:bloquead[oa]|blocked)[\s\S]{0,100}firewall/i.test(text);}
function retryDelay(value,text='',now=Date.now()){
 if(value){const v=String(value).trim();if(/^\d+$/.test(v))return Math.max(1000,Number(v)*1000);const date=Date.parse(v);if(Number.isFinite(date)&&date>now)return date-now;}
 const spanish=/(?:bloqueo\s+dura|espera|wait)\s*(\d{1,5})\s*(?:segundos|seconds)/i.exec(text);return spanish?Math.max(1000,Number(spanish[1])*1000+5000):65000;
}
module.exports={rateBlocked,retryDelay};
