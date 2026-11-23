"""23/11/2026: second signature of the channel with the NEW key (ZZ_DATA_SIGNING_KEY_V2).

The four channels (root, voe/, extra/, latino/) keep their channel.json signed with the old key, so installed apps
work exactly as before. Each one also gets channel-v2.json: the SAME payload (same index, same immutable files)
signed with the new key, read by apps that carry public-key-v2.der. When every app reads V2, channel.json stops
being signed with the old key (separate step)."""
import json
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

PREFIXES = ('', 'voe/', 'extra/', 'latino/')


def public_der(key):
    return key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def add(files, old_public, new_private_pem, new_public, raw):
    """Adds prefix+'channel-v2.json' next to every prefix+'channel.json'. Returns the names added.
    Without the V2 secret it adds nothing (the channel works as before); with a wrong one it stops."""
    if not new_private_pem:
        return []
    key = serialization.load_pem_private_key(new_private_pem.encode(), None)
    if public_der(key) != new_public:
        raise ValueError('V2 signing secret does not match public-key-v2.der')
    if new_public == old_public:
        raise ValueError('V2 must use a different key')
    old = serialization.load_der_public_key(old_public)
    added = []
    for prefix in PREFIXES:
        body = files.get(prefix + 'channel.json')
        if body is None:
            continue
        wrapper = json.loads(body)
        payload = wrapper['payload'].encode('utf-8')
        # Only what the old key really signed is signed again.
        old.verify(bytes.fromhex(wrapper['signature']), payload, padding.PKCS1v15(), hashes.SHA256())
        files[prefix + 'channel-v2.json'] = raw({'payload': wrapper['payload'], 'signature': key.sign(payload, padding.PKCS1v15(), hashes.SHA256()).hex()})
        added.append(prefix + 'channel-v2.json')
    return added
