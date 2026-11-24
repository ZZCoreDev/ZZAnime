// 24/11/2026 (Robin): informe de actualizaciones para la zona «Actualizaciones» del editor.
//  node informe.mjs github <salida.json>            → PR abiertas de Dependabot, sus pruebas y si son «seguras»
//  node informe.mjs merge <entrada.json> <salida.json> → integra SOLO las seguras (orden de «Actualizar todo lo seguro»)
//  node informe.mjs pc <salida.json>                 → valida el informe del PC (variable INFORME_PC, base64 de JSON)
// «Segura» = pruebas en verde + no es un salto grande (major) + no es torch/transformers/huggingface + no toca las tareas
// de .github (eso lo integra Robin a mano). Sin dependencias: solo fetch de Node 22 y el GITHUB_TOKEN de la tarea.
import fs from 'node:fs';
const [mode, a, b] = process.argv.slice(2);
const repo = process.env.GITHUB_REPOSITORY, token = process.env.GH_TOKEN;
async function gh(path, init = {}) {
 const r = await fetch('https://api.github.com/repos/' + repo + path, {...init, headers: {authorization: 'Bearer ' + token, accept: 'application/vnd.github+json', 'x-github-api-version': '2022-11-28', ...(init.headers || {})}});
 if (!r.ok) throw Error(path + ' → ' + r.status);
 return r.status === 204 ? null : r.json();
}
const major = v => Number(String(v || '').replace(/^v/, '').split('.')[0]);
export function classify(pr, files, checks) {
 const m = pr.title.match(/from (\S+) to (\S+)/), from = m?.[1] || null, to = m?.[2] || null;
 const run = checks.find(c => c.name === 'pruebas'), tests = !run ? 'sin pruebas' : run.status !== 'completed' ? 'en marcha' : run.conclusion === 'success' ? 'verde' : 'rojo';
 const isMajor = from && to ? major(to) > major(from) : /major/i.test(pr.title);
 const doblaje = /voz-doblaje|\btorch|transformers|huggingface/i.test(pr.title + ' ' + (pr.head?.ref || ''));
 const workflows = files.some(f => f.filename.startsWith('.github/workflows/'));
 const eco = /github_actions/.test(pr.head?.ref) ? 'acciones' : /npm_and_yarn/.test(pr.head?.ref) ? 'nube (Node)' : /pip/.test(pr.head?.ref) ? 'doblaje (Python)' : /docker/.test(pr.head?.ref) ? 'Docker' : 'otro';
 const why = tests !== 'verde' ? 'pruebas ' + tests : isMajor ? 'salto grande' : doblaje ? 'voz y doblaje' : workflows ? 'toca las tareas de GitHub (a mano)' : '';
 return {number: pr.number, title: pr.title.slice(0, 200), url: pr.html_url, ecosystem: eco, from, to, tests, major: !!isMajor, doblaje, workflows, safe: !why, why};
}
async function report() {
 const prs = (await gh('/pulls?state=open&per_page=50')).filter(p => p.user?.login === 'dependabot[bot]');
 const out = [];
 for (const pr of prs) {
  const files = await gh('/pulls/' + pr.number + '/files?per_page=100');
  const checks = (await gh('/commits/' + pr.head.sha + '/check-runs?per_page=50')).check_runs || [];
  out.push(classify(pr, files, checks));
 }
 return {schema: 1, checkedAt: new Date().toISOString(), prs: out};
}
if (mode === 'github') fs.writeFileSync(a, JSON.stringify(await report()));
if (mode === 'merge') {
 const now = await report(), done = [], failed = [];
 for (const p of now.prs.filter(p => p.safe)) {
  try { await gh('/pulls/' + p.number + '/merge', {method: 'PUT', body: JSON.stringify({merge_method: 'squash'})}); done.push(p.number); }
  catch (e) { failed.push({number: p.number, error: String(e.message).slice(0, 120)}); }
 }
 fs.writeFileSync(b, JSON.stringify({merged: done, failed, waiting: now.prs.filter(p => !p.safe).map(p => ({number: p.number, why: p.why}))}));
}
if (mode === 'pc') {
 // Solo se guarda lo que esperamos, con tamaños acotados (lo manda el PC de Robin con gh workflow run).
 const raw = JSON.parse(Buffer.from(process.env.INFORME_PC || '', 'base64').toString('utf8'));
 const s = (v, n) => String(v ?? '').replace(/[\x00-\x1f\x7f]/g, ' ').slice(0, n);
 if (!Array.isArray(raw.projects) || raw.projects.length > 20) throw Error('informe del PC no válido');
 const projects = raw.projects.map(p => ({name: s(p.name, 60), kind: s(p.kind, 20),
  outdated: (Array.isArray(p.outdated) ? p.outdated : []).slice(0, 80).map(o => ({name: s(o.name, 80), current: s(o.current, 40), wanted: s(o.wanted, 40), latest: s(o.latest, 40)})),
  vulnerabilities: Object.fromEntries(['low', 'moderate', 'high', 'critical'].map(k => [k, Math.max(0, Math.min(9999, Number(p.vulnerabilities?.[k]) || 0))])),
  error: p.error ? s(p.error, 200) : undefined}));
 fs.writeFileSync(a, JSON.stringify({schema: 1, checkedAt: new Date().toISOString(), projects}));
}
