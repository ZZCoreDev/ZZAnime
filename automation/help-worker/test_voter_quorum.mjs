// 12/11 auditoría M-07: the quorum counts ACCOUNTS (server-side voter hash), not devices or networks.
import assert from 'node:assert/strict';
import {Store} from './logic.js';
let DatabaseSync;try{({DatabaseSync}=await import('node:sqlite'));}catch{console.log('voter quorum SKIPPED (node:sqlite)');process.exit(0);}
function sqlite(){const db=new DatabaseSync(':memory:');return {exec(q,...p){const s=db.prepare(q);if(/^\s*SELECT/i.test(q))return {toArray:()=>s.all(...p).map(r=>({...r}))};s.run(...p);return {toArray:()=>[]};}};}
const ep='https://jkanime.net/frieren/1/',opt={name:'Streamwish',family:'streamwish',url:'https://streamwish.com/e/abcdefgh1234',okey:'k1'};
const item=(device,asn,voter)=>({episode:ep,device,asn,zone:'z'+asn,voter,options:[opt]});
const now=Date.now(),limits=[['x',1e9,1]];
{const s=new Store(sqlite());
 for(const [d,a] of [['d1',1],['d2',2],['d3',3]])s.submit([item(d,a,'v:ONE')],limits,now+1e9,now);
 const t=[...s.tally(ep).values()][0];assert.equal(t.voters.size,1);assert.equal(t.devices.size,3);assert.equal(Store.quorum(t,0),false,'one account, 3 devices, 3 networks: no quorum');
 const r=s.submit([item('d4',4,'v:TWO')],limits,now+1e9,now);assert.equal(Store.quorum([...s.tally(ep).values()][0],0),true,'second account: quorum');
 assert.equal(r.inspect.length,1);assert.equal(r.inspect[0].asns,2,'networks counted at most once per account');assert.equal(r.inspect[0].devices,2);}
{const s=new Store(sqlite());// rows without voter (stored before M-07) keep counting as devices
 s.submit([item('old1',1,undefined)],limits,now+1e9,now);s.submit([item('old2',2,undefined)],limits,now+1e9,now);
 assert.equal(Store.quorum([...s.tally(ep).values()][0],0),true,'historical rows unchanged');}
// 12/11 (novena revisión, opcional): one network per voter. A on ASN 1,2,3 and B, C only on ASN 1 = 2 paired networks, not 3.
{const s=new Store(sqlite());
 for(const [d,a] of [['a1',1],['a2',2],['a3',3]])s.submit([item(d,a,'v:A')],limits,now+1e9,now);
 s.submit([item('b1',1,'v:B')],limits,now+1e9,now);const r=s.submit([item('c1',1,'v:C')],limits,now+1e9,now);
 const t=[...s.tally(ep).values()][0];assert.equal(t.voters.size,3);assert.equal(t.asns.size,3);assert.equal(Store.paired(t,'asns'),2,'only two accounts can each bring a different network');
 assert.ok(r.inspect.every(c=>c.asns<=2),'decision records 2 networks, so quorum3 (3 networks) is not reached');}
{const s=new Store(sqlite());for(const [d,a,v] of [['x1',1,'v:X'],['y1',2,'v:Y'],['z1',3,'v:Z']])s.submit([item(d,a,v)],limits,now+1e9,now);
 assert.equal(Store.paired([...s.tally(ep).values()][0],'asns'),3,'three accounts on three networks: 3');}
console.log('M-07 voter quorum PASS (con emparejamiento cuenta-red)');
