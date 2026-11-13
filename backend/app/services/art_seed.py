import hmac
import base58
from .canonical_data import sha

GENESIS_HASH = sha(b"NEAR_ECHOES_GENESIS_V1").hex()

def u64(value: int):
    return value.to_bytes(8, "big", signed=False)

def master_seed(epoch, merkle_root, block_hash, randomness, previous_hash=GENESIS_HASH):
    block = base58.b58decode(block_hash)
    fields = [bytes.fromhex(merkle_root), block, bytes.fromhex(randomness), bytes.fromhex(previous_hash)]
    if any(len(f) != 32 for f in fields):
        raise ValueError("Seed inputs must decode to 32 bytes")
    return sha(b"NEAR_ECHOES_ART_V1" + u64(epoch) + b"".join(fields)).hex()

def random_value(seed, label, index):
    digest = hmac.digest(bytes.fromhex(seed), label.encode("ascii") + b":" + u64(index), "sha256")
    return int.from_bytes(digest[:8], "big") / 2**64
