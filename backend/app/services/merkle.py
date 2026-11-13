from .canonical_data import sha, record_hash

EMPTY_ROOT = sha(b"ECHO_EMPTY_V1")

def levels(records):
    tree = [[sha(b"\x00" + record_hash(r)) for r in records]]
    if not records:
        return [[EMPTY_ROOT]]
    while len(tree[-1]) > 1:
        row = tree[-1]
        tree.append([sha(b"\x01" + row[i] + row[min(i+1, len(row)-1)]) for i in range(0, len(row), 2)])
    return tree

def root(records):
    return levels(records)[-1][0].hex()

def proof(records, index):
    if not 0 <= index < len(records):
        raise ValueError("Invalid proof index")
    return proof_from_levels(levels(records),index)

def proof_from_levels(tree,index):
    if not tree or not 0<=index<len(tree[0]):raise ValueError("Invalid proof index")
    result = []
    for row in tree[:-1]:
        sibling = index ^ 1
        result.append({"hash": row[min(sibling, len(row)-1)].hex(), "side": "left" if index % 2 else "right"})
        index //= 2
    return result

def proof_index(records):
    tree=levels(records)
    return {"format":"echo-merkle-index-v1","leaf_count":len(records),"odd_leaf_policy":"duplicate_last",
            "levels":[[node.hex() for node in row] for row in tree]}

def verify(record, siblings, expected):
    node = sha(b"\x00" + record_hash(record))
    for item in siblings:
        if item["side"] not in ("left", "right"):
            return False
        other = bytes.fromhex(item["hash"])
        if len(other) != 32:
            return False
        node = sha(b"\x01" + (other + node if item["side"] == "left" else node + other))
    return node.hex() == expected
