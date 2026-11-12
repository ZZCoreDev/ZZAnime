// 13/11/2026 (Robin, riesgos 2/4/5): new series per connection and day, every account added up; IPv6 counted by /64.
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {Quota,linkAllows,netOf,forgetBans} from './quota.mjs';
for(const [ip,net] of [['203.0.113.7','203.0.113.7'],['2001:db8:1:2:aaaa:bbbb:cccc:dddd','2001:db8:1:2::'],['2001:DB8:1:2::9','2001:db8:1:2::'],['2001:db8::1','2001:db8:0:0::'],
 ['::1','0:0:0:0::'],['','' ],['basura',''],['2001:db8::1::2',''],['1.2.3','']])assert.equal(netOf(ip),net,ip);
assert.equal(netOf('2001:db8:1:2:1::'),netOf('2001:db8:1:2:ffff:ffff:ffff:ffff'),'same /64 = same connection');
function quota(){const db=new DatabaseSync(':memory:');const obj=new Quota({storage:{sql:{exec(q,...b){const s=db.prepare(q);if(/^\s*select/i.test(q)){const r=s.all(...b);return {toArray:()=>r};}s.run(...b);return {toArray:()=>[]};}}}});return {idFromName:n=>n,get:()=>({fetch:u=>obj.fetch(new Request(u))})};}
forgetBans();
// boxes out of the way (soft/burst high) to look only at the connection cap: 5 per connection, 4 per account
const env={QUOTA:quota(),LINK_RULES:'enforce',LINK_SOFT:'100',LINK_BURST:'100',LINK_DAY:'4',LINK_IP_DAY:'5',LINK_BAN:'1000'};
const open=(user,item,ip)=>linkAllows(env,{user,item,ip});
for(const i of [1,2,3,4])assert.equal(await open('a','s'+i,'203.0.113.7'),'ok','account a '+i);
assert.equal(await open('a','s5','203.0.113.7'),'limit','account cap 4');
assert.equal(await open('b','s1','203.0.113.7'),'ok','series already opened from this connection: not counted again');
assert.equal(await open('b','s9','203.0.113.7'),'ok','5th series of the connection');
assert.equal(await open('c','s10','203.0.113.7'),'limit','a new account on the same connection: stopped');
assert.equal(await open('b','s9','203.0.113.7'),'ok','reopening stays free');
assert.equal(await open('d','s11','2001:db8:1:2::1'),'ok','another connection is not affected');
// IPv6: changing the address inside the /64 does not help
{for(let i=2;i<=5;i++)assert.equal(await open('v'+i,'x'+i,'2001:db8:1:2::'+i),'ok');
 assert.equal(await open('v9','x9','2001:db8:1:2:dead:beef::9'),'limit','same /64, other address: same connection');}
// without a readable connection only the account limits apply
assert.equal(await open('e','s20',''),'ok');
// off unless enforce
assert.equal(await linkAllows({...env,LINK_RULES:'count'},{user:'f',item:'s30',ip:'203.0.113.7'}),'ok');
console.log('tope por conexión: suma cuentas, IPv6 por /64, reabrir gratis OK');
