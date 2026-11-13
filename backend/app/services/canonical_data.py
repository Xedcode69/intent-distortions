"""Redacted canonical echo-record-v1. Monetary values are decimal strings."""
import hashlib
from decimal import Decimal, InvalidOperation
import rfc8785

def canonical(value) -> bytes:
    return rfc8785.dumps(value)

def sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def money(value):
    if value is None or value == "":
        return None
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError("Monetary values must be decimal strings, not floats")
    try:
        d = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal amount") from exc
    if not d.is_finite() or d < 0 or len(str(value)) > 100 or abs(d.as_tuple().exponent)>36 or d.adjusted()>36:
        raise ValueError("Invalid decimal amount")
    return format(d, "f")

def record_key(raw: dict) -> str:
    # Deposit address+memo is the documented pagination identity. Hash locally;
    # neither address nor memo is published. Do NOT deduplicate on a shared tx hash.
    if not raw.get("depositAddress"):
        raise ValueError("Ambiguous record: no documented deposit identity")
    identity = [raw["depositAddress"], raw.get("depositMemo")]
    return sha(b"ECHO_ID_V1" + canonical(identity)).hex()

def normalize(raw: dict) -> dict:
    t = raw.get("createdAtTimestamp")
    if type(t) is not int or t < 0 or t > 9007199254740991:
        raise ValueError("createdAtTimestamp must be exact Unix seconds")
    for field in ("originAsset", "destinationAsset"):
        if not isinstance(raw.get(field), str) or not raw[field] or len(raw[field])>512:
            raise ValueError(f"Missing {field}: masking/non-swap record excluded")
    return dict(schema_version="echo-record-v1", created_at_unix=t,
                origin_asset=raw["originAsset"], destination_asset=raw["destinationAsset"],
                public_record_identifier=record_key(raw),
                amount_in_usd=money(raw.get("amountInUsd")), amount_out_usd=money(raw.get("amountOutUsd")))

def snapshot(raw_records: list[dict], start: int, end: int, *, start_ns=None, end_ns=None) -> list[dict]:
    if start >= end:
        raise ValueError("Invalid half-open epoch interval")
    records = {}
    for raw in raw_records:
        if raw.get("status") != "SUCCESS":
            continue
        record = normalize(raw)
        t_ns=record["created_at_unix"]*1_000_000_000
        lower=start_ns if start_ns is not None else start*1_000_000_000
        upper=end_ns if end_ns is not None else end*1_000_000_000
        if not lower <= t_ns < upper:
            continue
        key = record["public_record_identifier"]
        if key in records and records[key] != record:
            raise ValueError("Conflicting deposit identity requires reconciliation")
        records[key] = record
    return sorted(records.values(), key=lambda r: (r["created_at_unix"], r["public_record_identifier"]))

def record_hash(record: dict) -> bytes:
    return sha(b"ECHO_RECORD_V1" + canonical(record))

def validate_snapshot(records,start_ns,end_ns):
    """Validate a redacted observation without recreating private deposit identities."""
    fields={"schema_version","created_at_unix","origin_asset","destination_asset","public_record_identifier","amount_in_usd","amount_out_usd"}
    keys=set()
    for r in records:
        if set(r)!=fields or r["schema_version"]!="echo-record-v1":raise ValueError("Invalid canonical record schema")
        if type(r["created_at_unix"]) is not int or not start_ns<=r["created_at_unix"]*10**9<end_ns:raise ValueError("Snapshot record outside exact checkpoint interval")
        key=r["public_record_identifier"]
        if len(key)!=64 or any(c not in "0123456789abcdef" for c in key) or key in keys:raise ValueError("Duplicate or invalid record identity")
        keys.add(key)
        if any(not isinstance(r[k],str) or not r[k] or len(r[k])>512 for k in ["origin_asset","destination_asset"]):raise ValueError("Invalid asset identifier")
        for k in ["amount_in_usd","amount_out_usd"]:
            if money(r[k])!=r[k]:raise ValueError("Noncanonical decimal amount")
    if records!=sorted(records,key=lambda r:(r["created_at_unix"],r["public_record_identifier"])):raise ValueError("Snapshot order mismatch")
    return records
