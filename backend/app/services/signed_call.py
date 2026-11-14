"""Strict decoder for the legacy Ed25519 transaction emitted by near-cli-rs.

Used only by the explicit prototype operator, never the HTTP service. Rejects
unsupported transaction/key variants before broadcasting anything.
"""
import base64
import hashlib
import json
import struct
import base58

def inspect_signed_call(encoded,expected):
    data=base64.b64decode(encoded,validate=True)
    if len(data)>60000:raise ValueError('Signed call exceeds budget')
    offset=0
    def take(n):
        nonlocal offset
        if n<0 or offset+n>len(data):raise ValueError('Truncated signed transaction')
        value=data[offset:offset+n];offset+=n;return value
    def integer(size):return int.from_bytes(take(size),'little')
    def vector():
        length=integer(4)
        if length>50000:raise ValueError('Transaction field exceeds budget')
        return take(length)
    signer=vector().decode()
    if integer(1)!=0:raise ValueError('Prototype signer requires classic Ed25519')
    public_key=take(32);nonce=integer(8);receiver=vector().decode();block_hash=take(32)
    if integer(4)!=1 or integer(1)!=2:raise ValueError('Expected exactly one FunctionCall action')
    method=vector().decode();args=json.loads(vector());gas=integer(8);deposit=integer(16)
    unsigned=data[:offset]
    if integer(1)!=0 or len(take(64))!=64 or offset!=len(data):raise ValueError('Unexpected signature encoding')
    if (signer!=expected['signer'] or receiver!=expected['contract'] or method!=expected['method']
        or args!=expected['args'] or deposit!=int(expected['deposit_yocto']) or gas!=expected['gas']):
        raise ValueError('Signed transaction differs from authorized call')
    return {'transaction_hash':base58.b58encode(hashlib.sha256(unsigned).digest()).decode(),'nonce':nonce,
            'public_key':'ed25519:'+base58.b58encode(public_key).decode(),'block_hash':base58.b58encode(block_hash).decode()}
