"""Unbiased, replayable family selection; independent of the AI styling response."""
import hmac
from .art_seed import u64

FAMILIES=("orbital_network","fractal_branches","crystalline","flow_field","spiral_constellation","particle_nebula")
POLICY="seed-rejection-six-v1"


def select_family(seed):
    key=bytes.fromhex(seed)
    if len(key)!=32:raise ValueError("Family selection requires a 32-byte art seed")
    limit=2**256-(2**256%len(FAMILIES));counter=0
    while True:
        digest=hmac.digest(key,b"NEAR_ECHOES_FAMILY_V1"+u64(counter),"sha256")
        value=int.from_bytes(digest,"big")
        if value<limit:
            index=value%len(FAMILIES)
            return {"policy":POLICY,"family":FAMILIES[index],"index":index,"counter":counter,"digest":digest.hex()}
        counter+=1
