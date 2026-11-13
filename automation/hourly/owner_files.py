"""9/11/2026: the editor's view of link health and help status, for the OWNER only.

These files used to be read from the public provider-data branch. The links now live in the private repository
ZZAnime-datos, so the editor gets them from zzanime-respaldo under /owner/, which channel_gate.mjs answers only
for the editor owner (Supabase zz_editor_access with authenticator). Only what the editor shows is kept: dead
links (episode, provider, url, date, excluded) and the summary of the last check. Parts stay under 1.5 MB."""
import json,os,urllib.request
from pathlib import Path
from no_redirect import NO_REDIRECT

PART = 1_500_000
KEEP = ('episode', 'family', 'name', 'url', 'checkedAt', 'excluded', 'state')


def raw(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()


def cloud_runs(token, fetch=None):
    """10/11/2026: the latest cloud tasks for the editor's «Nube» card. The editor asked GitHub directly and ran out of
    the 60 anonymous requests per hour shared by the owner's connection; the cloud asks with its own token instead.
    Only name, state and dates are kept. None when GitHub cannot be read."""
    url = 'https://api.github.com/repos/ZZCoreDev/ZZAnime/actions/runs?per_page=60'
    try:
        if fetch:
            data = fetch(url)
        else:
            req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'ZZAnime-Nube/1'})
            with NO_REDIRECT.open(req, timeout=20) as r:
                data = json.loads(r.read())
        keep = ('name', 'status', 'conclusion', 'updated_at', 'workflow_id', 'html_url')
        return {'workflow_runs': [{k: run.get(k) for k in keep} for run in data.get('workflow_runs', [])]}
    except Exception:
        return None


def semaforo(folder, health, now):
    """14/11/2026 (Robin): traffic light of the editor's Sistema. Servers: per family, the links checked in the 48 hours
    before the last check (alive / dead / unknown). JK copy: the last batch the PC sent and the cloud imported. Only
    counts and dates; no link leaves here."""
    out = {'schema': 1, 'builtAt': now, 'servers': {}, 'jk': None}
    last = (health or {}).get('last') or {}
    edge = float(last.get('checkedAt') or 0) - 48 * 3600
    for v in ((health or {}).get('links') or {}).values():
        if float(v.get('checkedAt') or 0) < edge:
            continue
        fam = str(v.get('family') or '?')[:20]
        row = out['servers'].setdefault(fam, {'alive': 0, 'dead': 0, 'unknown': 0})
        state = v.get('state')
        row[state if state in ('alive', 'dead') else 'unknown'] += 1
    out['serversCheckedAt'] = last.get('checkedAt')
    pc = Path(folder) / 'pc-import-status.json'
    if pc.exists():
        try:
            x = json.loads(pc.read_bytes())
            out['jk'] = {k: x.get(k) for k in ('checkedAt', 'state', 'imported', 'series')}
        except ValueError:
            pass
    return out


def popular(folder):
    """14/11/2026 (Robin): «Lo más visto» of the editor's Resumen: series and how many different devices / networks
    watched them (play-stats.json, devices older than 24 h). Only JK series addresses and counts; nothing personal."""
    path = Path(folder) / 'play-stats.json'
    if not path.exists():
        return None
    try:
        x = json.loads(path.read_bytes())
    except ValueError:
        return None
    rows = []
    for r in x.get('popular') or []:
        s = r.get('series')
        if isinstance(s, str) and s.startswith('https://jkanime.net/') and len(s) < 200:
            rows.append({'series': s, 'devices': int(r.get('devices') or 0), 'networks': int(r.get('independentNetworks') or 0)})
    return {'schema': 1, 'checkedAt': x.get('checkedAt'), 'minDeviceAgeHours': x.get('minDeviceAgeHours'), 'popular': rows[:50]}


def build(folder, token=None, fetch=None):
    """{published name: bytes} for the owner; empty when the state files are absent."""
    folder = Path(folder)
    out = {}
    token = token if token is not None else os.environ.get('GH_TOKEN', '')
    runs = cloud_runs(token, fetch) if token else None
    if runs is not None:
        out['owner/cloud-runs.json'] = raw(runs)
    import time
    health_file = folder / 'link-health.json'
    out['owner/semaforo.json'] = raw(semaforo(folder, json.loads(health_file.read_bytes()) if health_file.exists() else None, time.time()))
    seen = popular(folder)
    if seen is not None:
        out['owner/popular.json'] = raw(seen)
    help_status = folder / 'help-status.json'
    if help_status.exists():
        out['owner/help-status.json'] = raw(json.loads(help_status.read_bytes()))
    health_path = folder / 'link-health.json'
    if not health_path.exists():
        return out
    health = json.loads(health_path.read_bytes())
    dead = {key: {k: v[k] for k in KEEP if k in v} for key, v in sorted((health.get('links') or {}).items()) if v.get('state') == 'dead'}
    parts, current, size = [], {}, 0
    for key, value in dead.items():
        cost = len(raw({key: value}))
        if current and size + cost > PART:
            parts.append(current)
            current, size = {}, 0
        current[key] = value
        size += cost
    if current or not parts:
        parts.append(current)
    if len(parts) > 40:
        raise ValueError('Owner link health too large')
    for number, links in enumerate(parts):
        out[f'owner/link-health-{number}.json'] = raw({'schema': 1, 'part': number, 'links': links})
    out['owner/link-health.json'] = raw({'schema': 1, 'parts': len(parts), 'last': health.get('last') or {}})
    return out
