'use strict';
const assert=require('assert'),{FailureCache}=require('./source_failure_cache.cjs');let now=1000,checks=0;
const ok=x=>{checks++;assert.ok(x)},c=new FailureCache(3,()=>now);
c.remember('https://jkanime.net/a/',403);ok(c.get('https://jkanime.net/b/').status===403);ok(!c.get('https://tioanime.com/anime/b'));
c.remember('https://tioanime.com/anime/a',404);ok(c.get('https://tioanime.com/anime/a').status===404);ok(!c.get('https://tioanime.com/anime/b'));ok(!c.get('https://tioanime.com/ver/a-1'));
c.remember('https://vww.animeflv.one/ver/a-1',404);ok(!c.get('https://vww.animeflv.one/ver/a-1'));
c.remember('https://vww.animeflv.one/anime/a',200);ok(!c.get('https://vww.animeflv.one/anime/a'));
now+=60001;ok(!c.get('https://jkanime.net/a/'));ok(!!c.get('https://tioanime.com/anime/a'));
now+=240000;ok(!c.get('https://tioanime.com/anime/a'));
c.remember('https://jkanime.net/a/',403,'120');now+=61000;ok(!!c.get('https://jkanime.net/b/'));now+=60000;ok(!c.get('https://jkanime.net/b/'));
for(let i=0;i<10;i++)c.remember('https://tioanime.com/anime/a'+i,404);ok(c.rows.size===3);
let network=0;const p=new FailureCache(10,()=>now);
function query(url,status){if(p.get(url))return;network++;p.remember(url,status);}
for(let round=0;round<2;round++)for(const name of ['series-a','series-b']){query('https://jkanime.net/'+name+'/',403);query('https://tioanime.com/anime/'+name,404);query('https://vww.animeflv.one/anime/'+name,404);}
ok(network===5);ok(network<12);
console.log(checks+' cache scope / expiry / Retry-After / two-series controls PASS; 12 simulated failed requests -> 5');
