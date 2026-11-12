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
console.log('M-07 voter quorum PASS');
