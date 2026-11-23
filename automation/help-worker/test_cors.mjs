// 23/11/2026: la web (solo https://zzanime.uk) puede llamar a /v1/dead; nada más se abre al navegador.
import assert from 'node:assert/strict';
import {withWebCors,webCors} from './logic.js';
const ok=()=>new Response('{"accepted":false,"reason":"login"}',{status:401,headers:{'content-type':'application/json'}});
const pre=await withWebCors(new Request('https://ayuda.zzanime.uk/v1/dead',{method:'OPTIONS',headers:{Origin:'https://zzanime.uk'}}),()=>{throw Error('no debe llegar');});
assert.equal(pre.status,204);assert.equal(pre.headers.get('access-control-allow-origin'),'https://zzanime.uk');assert.match(pre.headers.get('access-control-allow-headers'),/authorization/);
assert.equal(webCors(new Request('https://ayuda.zzanime.uk/v1/dead',{method:'POST',headers:{Origin:'https://evil.example'}})),false,'otro origen');
assert.equal(webCors(new Request('https://ayuda.zzanime.uk/v1/play',{method:'POST',headers:{Origin:'https://zzanime.uk'}})),false,'otra ruta');
const r=await withWebCors(new Request('https://ayuda.zzanime.uk/v1/dead',{method:'POST',headers:{Origin:'https://zzanime.uk'}}),ok);
assert.equal(r.status,401,'la sesión sigue siendo obligatoria');assert.equal(r.headers.get('access-control-allow-origin'),'https://zzanime.uk');
const other=await withWebCors(new Request('https://ayuda.zzanime.uk/v1/dead',{method:'POST',headers:{Origin:'https://evil.example'}}),ok);
assert.equal(other.headers.get('access-control-allow-origin'),null);
console.log('ok test_cors');
