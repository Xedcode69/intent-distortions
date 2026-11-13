"""Only the published default drand BLS12-381 chained network is accepted."""
import hashlib
import httpx
from py_ecc.bls import G2Basic
from .art_seed import u64

CHAIN_HASH = "8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce"
# Pinned League of Entropy default network. Never trust a key supplied in an API response.
PUBLIC_KEY = "868f005eb8e6e4ca0a47c8a77ceaa5309a47978a7c71bc5cce96366b5d7a569937c529eeda66c7293784a9402801af31"
GENESIS_TIME = 1595431050
PERIOD = 30

def round_for(release_time: int):
    # First round released at or after scheduled Sunday 18:00 UTC.
    return (release_time - GENESIS_TIME + PERIOD - 1) // PERIOD + 1

def verify_beacon(beacon: dict, expected_round: int):
    if beacon.get("round") != expected_round or expected_round < 1:
        raise ValueError("Unexpected drand round")
    if beacon.get("chain_hash", CHAIN_HASH) != CHAIN_HASH:
        raise ValueError("Untrusted drand network")
    sig = bytes.fromhex(beacon["signature"])
    previous = bytes.fromhex(beacon["previous_signature"])
    if len(sig) != 96 or len(previous) != 96:
        raise ValueError("Invalid chained beacon lengths")
    message = hashlib.sha256(previous + u64(expected_round)).digest()
    if not G2Basic.Verify(bytes.fromhex(PUBLIC_KEY), message, sig):
        raise ValueError("Invalid drand BLS signature")
    randomness = hashlib.sha256(sig).hexdigest()
    if randomness != beacon["randomness"]:
        raise ValueError("Randomness does not match signature")
    return {**beacon, "chain_hash": CHAIN_HASH, "network": "default", "verified": True,
            "released_at": GENESIS_TIME + (expected_round-1)*PERIOD}

async def fetch_beacon(release_time):
    rnd = round_for(release_time)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"https://api.drand.sh/{CHAIN_HASH}/public/{rnd}")
        response.raise_for_status()
        return verify_beacon(response.json(), rnd)

def select_timestamp(epoch: int, randomness: str, window_start: int, duration=17*3600):
    if duration <= 0 or duration > 2**64:
        raise ValueError("Invalid selection window")
    data = bytes.fromhex(randomness)
    if len(data) != 32:
        raise ValueError("Invalid randomness length")
    seed = hashlib.sha256(b"NEAR_ECHOES_BLOCK_SELECTION_V1" + u64(epoch) + data).digest()
    limit = 2**256 - (2**256 % duration)
    candidate, counter = int.from_bytes(seed, "big"), 0
    while candidate >= limit:
        counter += 1
        candidate = int.from_bytes(hashlib.sha256(b"NEAR_ECHOES_REJECT_V1" + seed + u64(counter)).digest(), "big")
    return window_start + candidate % duration
