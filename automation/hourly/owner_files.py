"""9/11/2026: the editor's view of link health and help status, for the OWNER only.

These files used to be read from the public provider-data branch. The links now live in the private repository
ZZAnime-datos, so the editor gets them from zzanime-respaldo under /owner/, which channel_gate.mjs answers only
for the editor owner (Supabase zz_editor_access with authenticator). Only what the editor shows is kept: dead
links (episode, provider, url, date, excluded) and the summary of the last check. Parts stay under 1.5 MB."""
import json
from pathlib import Path

PART = 1_500_000
KEEP = ('episode', 'family', 'name', 'url', 'checkedAt', 'excluded', 'state')


def raw(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()


def build(folder):
    """{published name: bytes} for the owner; empty when the state files are absent."""
    folder = Path(folder)
    out = {}
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
