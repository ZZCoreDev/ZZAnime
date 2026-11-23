"""23/11/2026: channel-v2.json = same payload as channel.json, signed with the new key; nothing else changes."""
import json
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import channel_v2

def raw(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
def pem(k): return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
old, new, other = (rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(3))
old_pub, new_pub = channel_v2.public_der(old), channel_v2.public_der(new)
def signed(k, payload): return raw({'payload': payload.decode(), 'signature': k.sign(payload, padding.PKCS1v15(), hashes.SHA256()).hex()})
payload = raw({'schema': 1, 'sequence': 5, 'indexPath': 'indexes/x.bin'})
files = {'channel.json': signed(old, payload), 'voe/channel.json': signed(old, payload), 'series/a.bin': b'x'}
before = dict(files)

# Without the V2 secret nothing changes.
assert channel_v2.add(files, old_pub, '', new_pub, raw) == [] and files == before
# With it: one channel-v2.json per published channel, same payload, valid only with the new key.
added = channel_v2.add(files, old_pub, pem(new), new_pub, raw)
assert added == ['channel-v2.json', 'voe/channel-v2.json'], added
for name in before: assert files[name] == before[name], name
for name in added:
    w = json.loads(files[name]); assert w['payload'] == payload.decode()
    serialization.load_der_public_key(new_pub).verify(bytes.fromhex(w['signature']), payload, padding.PKCS1v15(), hashes.SHA256())
    try: serialization.load_der_public_key(old_pub).verify(bytes.fromhex(w['signature']), payload, padding.PKCS1v15(), hashes.SHA256()); raise AssertionError('old key must not verify V2')
    except Exception as e:
        if isinstance(e, AssertionError): raise
# A secret that is not the public-key-v2.der pair stops the publication.
try: channel_v2.add(dict(before), old_pub, pem(other), new_pub, raw); raise AssertionError('wrong secret accepted')
except ValueError: pass
# A channel.json not signed by the old key is never re-signed.
bad = {'channel.json': signed(other, payload)}
try: channel_v2.add(bad, old_pub, pem(new), new_pub, raw); raise AssertionError('foreign manifest re-signed')
except Exception as e:
    if isinstance(e, AssertionError): raise
    assert 'channel-v2.json' not in bad
print('ok test_channel_v2')
