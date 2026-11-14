"""Strict decoder for the legacy Ed25519 transaction emitted by near-cli-rs.

Used only by the explicit prototype operator, never the HTTP service. Rejects
unsupported transaction/key variants before broadcasting anything.
"""
import base64
import hashlib
import json
import struct
import base58

def inspect_signed_bootstrap(encoded,expected):
    data=base64.b64decode(encoded,validate=True)
    if len(data)>2_000_000:raise ValueError('Bootstrap exceeds budget')
    offset=0
    def take(n):
        nonlocal offset
        if n<0 or offset+n>len(data):raise ValueError('Truncated bootstrap')
        value=data[offset:offset+n];offset+=n;return value
    def integer(n):return int.from_bytes(take(n),'little')
    def vector():
        length=integer(4)
        if length>1_500_000:raise ValueError('Bootstrap field budget')
        return take(length)
    signer=vector().decode()
    if integer(1)!=0:raise ValueError('Ed25519 required')
    public=take(32);nonce=integer(8);receiver=vector().decode();block=take(32)
    if integer(4)!=4 or integer(1)!=0 or integer(1)!=3:raise ValueError('Create/fund/deploy/init only; no access keys')
    deposit=integer(16)
    if integer(1)!=1:raise ValueError('Deploy action required')
    code=vector()
    if integer(1)!=2:raise ValueError('Initializer required')
    method=vector().decode();args=json.loads(vector());gas=integer(8);attached=integer(16);unsigned=data[:offset]
    if integer(1)!=0:raise ValueError('Ed25519 signature required')
    take(64)
    if offset!=len(data) or (signer,receiver,deposit,hashlib.sha256(code).hexdigest(),method,args,gas,attached)!=(
        expected['signer'],expected['contract'],int(expected['deposit_yocto']),expected['code_sha256'],expected['method'],expected['args'],expected['gas'],0):
        raise ValueError('Bootstrap differs from reviewed plan')
    return {'transaction_hash':base58.b58encode(hashlib.sha256(unsigned).digest()).decode(),'nonce':nonce,
        'public_key':'ed25519:'+base58.b58encode(public).decode(),'block_hash':base58.b58encode(block).decode()}

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
