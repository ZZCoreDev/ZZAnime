'use strict';
const assert=require('assert'),p=require('./lib/fast-rules.cjs');let checks=0;
function good(title,expected,n){checks++;p.identity('<title>'+title+'</title>',expected,n);}
function bad(title,expected,n){checks++;assert.throws(()=>p.identity('<title>'+title+'</title>',expected,n));}
for(const apostrophe of ['&#39;','&#039;','&#00039;','&#x27;','&#X0027;','&apos;'])good('Vivy: Fluorite Eye'+apostrophe+'s Song episodio 1',"Vivy: Fluorite Eye's Song",1);
good('King&#039;s Raid: Ishi wo Tsugumono-tachi episodio 1',"King's Raid: Ishi wo Tsugumono-tachi",1);
good('A &amp; B episodio 2','A & B',2);good('A &quot;B&quot; episodio 2','A "B"',2);
bad('Vivy: Fluorite Eye&#039;s Song episodio 2',"Vivy: Fluorite Eye's Song",1);
bad('King&#039;s Raid: Different Season episodio 1',"King's Raid: Ishi wo Tsugumono-tachi",1);
bad('Vivy: Fluorite Eye&#xD800;s Song episodio 1',"Vivy: Fluorite Eye's Song",1);
bad('Vivy: Fluorite Eye&#0;s Song episodio 1',"Vivy: Fluorite Eye's Song",1);
bad('Vivy: Fluorite Eye&amp;#039;s Song episodio 1',"Vivy: Fluorite Eye's Song",1);
console.log(checks+' numeric HTML entity / chapter / identity controls PASS');
