import struct

# Precompute EDC table (CRC32 with polynomial 0xD8018001 reversed)
EDC_TABLE = []
for i in range(256):
    crc = i
    for _ in range(8):
        if crc & 1:
            crc = (crc >> 1) ^ 0xD8018001
        else:
            crc = crc >> 1
    EDC_TABLE.append(crc)

def compute_edc(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc = (crc >> 8) ^ EDC_TABLE[(crc ^ byte) & 0xFF]
    return crc

# Reed-Solomon over GF(2^8)
# Primitive polynomial: x^8 + x^4 + x^3 + x^2 + 1 (0x11D)
GF_EXP = [0] * 512
GF_LOG = [0] * 256

def init_gf():
    x = 1
    for i in range(255):
        GF_EXP[i] = x
        GF_EXP[i + 255] = x
        GF_LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D

init_gf()

def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return GF_EXP[GF_LOG[a] + GF_LOG[b]]

if __name__ == "__main__":
    print("GF initialized successfully. compute_edc(b'TEST') =", hex(compute_edc(b"TEST")))
