'use strict';
const a=require('assert'),d=require('./source-diagnostics.cjs');
const cases=[['Source HTTP 404','address-not-found'],['Source HTTP 302','redirect'],['Source HTTP 403','access-denied'],['Source HTTP 429','rate-limit'],['Ambiguous chapter identity','identity-mismatch'],['Missing source chapter','unlisted-episode'],['No existing approved provider','no-approved-provider'],['Missing observed options key','options-missing'],['Per-series listing budget','budget-limit'],['fetch failed','parser-or-network']];
for(const [message,cause] of cases){const result=d.failure('detail',Error(message));a.equal(result.cause,cause);a.equal(result.stage,'detail');}
a.equal(d.failure('options',Error('Source HTTP 404')).status,404);a.equal(d.failure('parse',Error('x'.repeat(1000))).message.length,160);
console.log('12 source diagnosis classification / bounded log controls PASS');
