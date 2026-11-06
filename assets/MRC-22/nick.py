#!/usr/bin/env python3
"""Build a keyless (Nick's method) pre-EIP-155 deployment transaction for the MRC-22 factory.

Usage:
    solc --strict-assembly --optimize --evm-version osaka --bin CreateBigFactory.yul \
        | awk '/Binary representation/{getline; print}' > initcode.hex
    python3 nick.py initcode.hex 1000000000000 300000 22

Arguments are the file containing the creation bytecode (hex), the gas price in wei, the gas
limit, and the byte (hex) repeated to form `r` and `s`. `r` is incremented until it is a valid
signature component. Requires `cast` (Foundry) for keccak256.
"""
import subprocess, sys

INITCODE = bytes.fromhex(open(sys.argv[1]).read().strip().removeprefix("0x"))
GAS_PRICE = int(sys.argv[2])
GAS_LIMIT = int(sys.argv[3])
SIG_BYTE = int(sys.argv[4], 16)  # r and s are this byte repeated, incremented until valid

def keccak(b: bytes) -> bytes:
    out = subprocess.run(["cast", "keccak", "0x" + b.hex()], capture_output=True, text=True, check=True).stdout.strip()
    return bytes.fromhex(out[2:])

def rlp_bytes(b: bytes) -> bytes:
    if len(b) == 1 and b[0] < 0x80:
        return b
    if len(b) <= 55:
        return bytes([0x80 + len(b)]) + b
    l = len(b).to_bytes((len(b).bit_length() + 7) // 8, "big")
    return bytes([0xB7 + len(l)]) + l + b

def rlp_list(items) -> bytes:
    body = b"".join(items)
    if len(body) <= 55:
        return bytes([0xC0 + len(body)]) + body
    l = len(body).to_bytes((len(body).bit_length() + 7) // 8, "big")
    return bytes([0xF7 + len(l)]) + l + body

def uint(n: int) -> bytes:
    return rlp_bytes(n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b"")

# secp256k1
P = 2**256 - 2**32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)

def add(a, b):
    if a is None: return b
    if b is None: return a
    if a[0] == b[0] and (a[1] + b[1]) % P == 0: return None
    if a == b:
        m = 3 * a[0] * a[0] * pow(2 * a[1], -1, P) % P
    else:
        m = (b[1] - a[1]) * pow(b[0] - a[0], -1, P) % P
    x = (m * m - a[0] - b[0]) % P
    return (x, (m * (a[0] - x) - a[1]) % P)

def mul(k, pt):
    r = None
    while k:
        if k & 1: r = add(r, pt)
        pt = add(pt, pt); k >>= 1
    return r

def recover(h: bytes, v: int, r: int, s: int):
    y2 = (pow(r, 3, P) + 7) % P
    y = pow(y2, (P + 1) // 4, P)
    if y * y % P != y2:
        return None  # r is not the x-coordinate of a curve point
    if y % 2 != (v - 27):
        y = P - y
    R = (r, y)
    z = int.from_bytes(h, "big")
    rinv = pow(r, -1, N)
    Q = mul(rinv, add(mul(s, R), mul((-z) % N, G)))
    pub = Q[0].to_bytes(32, "big") + Q[1].to_bytes(32, "big")
    return keccak(pub)[12:]

fields = [uint(0), uint(GAS_PRICE), uint(GAS_LIMIT), rlp_bytes(b""), uint(0), rlp_bytes(INITCODE)]
sighash = keccak(rlp_list(fields))

v = 27
r = int.from_bytes(bytes([SIG_BYTE]) * 32, "big")
s = r
assert s <= N // 2, "s must be in the lower half of the curve order"
while (sender := recover(sighash, v, r, s)) is None:
    r += 1

raw = rlp_list(fields + [uint(v), uint(r), uint(s)])
factory = keccak(rlp_list([rlp_bytes(sender), uint(0)]))[12:]

print("signing hash :", "0x" + sighash.hex())
print("v            :", v)
print("r            :", hex(r))
print("s            :", hex(s))
print("raw tx       :", "0x" + raw.hex())
print("raw tx hash  :", "0x" + keccak(raw).hex())
print("sender       :", "0x" + sender.hex())
print("factory      :", "0x" + factory.hex())
print("funding (wei):", GAS_PRICE * GAS_LIMIT)
