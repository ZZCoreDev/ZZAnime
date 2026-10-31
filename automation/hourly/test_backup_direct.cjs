'use strict';
// backup-rules direct(): mixdroop.bz/e/<id> (JS loader, blocked redirect) becomes mxdrop.click/e/<id>; nothing else changes.
const assert=require('assert'),r=require('./lib/backup-rules.cjs');
assert.equal(r.direct('MixDrop','https://mixdroop.bz/e/abcd1234'),'https://mxdrop.click/e/abcd1234');
assert.equal(r.direct('Mixdrop 2','https://www.mixdroop.bz/e/abcd1234'),'https://mxdrop.click/e/abcd1234');
for(const [n,u] of [['Streamwish','https://mixdroop.bz/e/abcd1234'],['MixDrop','https://mixdroop.bz.evil.example/e/abcd1234'],['MixDrop','https://mixdroop.bz/e/abcd1234?x=1'],['MixDrop','http://mixdroop.bz/e/abcd1234'],['MixDrop','https://mixdroop.bz/f/abcd1234'],['MixDrop','https://mixdrop.ps/e/abcd1234'],['MixDrop','not a url']])assert.equal(r.direct(n,u),u);
// The rewritten link is a regular MixDrop on a host every installed app accepts, not an extra option.
assert.equal(r.family('MixDrop'),'mixdrop');assert.equal(r.embed(r.direct('MixDrop','https://mixdroop.bz/e/abcd1234'),['mxdrop.click']),'https://mxdrop.click/e/abcd1234');
console.log('backup direct ok');
