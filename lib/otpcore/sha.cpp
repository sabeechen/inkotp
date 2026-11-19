#include "sha.h"

#include <string.h>

namespace otp {
namespace {

#include "sha_consts.inc"

inline uint32_t rol32(uint32_t x, int n) { return (x << n) | (x >> (32 - n)); }
inline uint32_t ror32(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }
inline uint64_t ror64(uint64_t x, int n) { return (x >> n) | (x << (64 - n)); }

inline uint32_t be32(const uint8_t* p) {
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}

inline uint64_t be64(const uint8_t* p) { return (uint64_t)be32(p) << 32 | be32(p + 4); }

struct Ctx {
    Algo algo;
    uint64_t total;  // bytes hashed so far
    size_t fill;     // bytes waiting in buf
    uint8_t buf[128];
    union {
        uint32_t h32[8];
        uint64_t h64[8];
    };
};

size_t blockSize(Algo algo) { return algo == Algo::SHA512 ? 128 : 64; }

void sha1Block(uint32_t* h, const uint8_t* p) {
    uint32_t w[80];
    for (int i = 0; i < 16; i++) w[i] = be32(p + 4 * i);
    for (int i = 16; i < 80; i++) w[i] = rol32(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
    uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
    for (int i = 0; i < 80; i++) {
        uint32_t f, k;
        if (i < 20) {
            f = (b & c) | (~b & d);
            k = 0x5A827999;
        } else if (i < 40) {
            f = b ^ c ^ d;
            k = 0x6ED9EBA1;
        } else if (i < 60) {
            f = (b & c) | (b & d) | (c & d);
            k = 0x8F1BBCDC;
        } else {
            f = b ^ c ^ d;
            k = 0xCA62C1D6;
        }
        uint32_t t = rol32(a, 5) + f + e + k + w[i];
        e = d;
        d = c;
        c = rol32(b, 30);
        b = a;
        a = t;
    }
    h[0] += a;
    h[1] += b;
    h[2] += c;
    h[3] += d;
    h[4] += e;
}

void sha256Block(uint32_t* h, const uint8_t* p) {
    uint32_t w[64];
    for (int i = 0; i < 16; i++) w[i] = be32(p + 4 * i);
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ror32(w[i - 15], 7) ^ ror32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ror32(w[i - 2], 17) ^ ror32(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint32_t v[8];
    memcpy(v, h, sizeof(v));
    for (int i = 0; i < 64; i++) {
        uint32_t s1 = ror32(v[4], 6) ^ ror32(v[4], 11) ^ ror32(v[4], 25);
        uint32_t ch = (v[4] & v[5]) ^ (~v[4] & v[6]);
        uint32_t t1 = v[7] + s1 + ch + kSha256K[i] + w[i];
        uint32_t s0 = ror32(v[0], 2) ^ ror32(v[0], 13) ^ ror32(v[0], 22);
        uint32_t maj = (v[0] & v[1]) ^ (v[0] & v[2]) ^ (v[1] & v[2]);
        uint32_t t2 = s0 + maj;
        memmove(v + 1, v, 7 * sizeof(v[0]));
        v[4] += t1;
        v[0] = t1 + t2;
    }
    for (int i = 0; i < 8; i++) h[i] += v[i];
}

void sha512Block(uint64_t* h, const uint8_t* p) {
    uint64_t w[80];
    for (int i = 0; i < 16; i++) w[i] = be64(p + 8 * i);
    for (int i = 16; i < 80; i++) {
        uint64_t s0 = ror64(w[i - 15], 1) ^ ror64(w[i - 15], 8) ^ (w[i - 15] >> 7);
        uint64_t s1 = ror64(w[i - 2], 19) ^ ror64(w[i - 2], 61) ^ (w[i - 2] >> 6);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    uint64_t v[8];
    memcpy(v, h, sizeof(v));
    for (int i = 0; i < 80; i++) {
        uint64_t s1 = ror64(v[4], 14) ^ ror64(v[4], 18) ^ ror64(v[4], 41);
        uint64_t ch = (v[4] & v[5]) ^ (~v[4] & v[6]);
        uint64_t t1 = v[7] + s1 + ch + kSha512K[i] + w[i];
        uint64_t s0 = ror64(v[0], 28) ^ ror64(v[0], 34) ^ ror64(v[0], 39);
        uint64_t maj = (v[0] & v[1]) ^ (v[0] & v[2]) ^ (v[1] & v[2]);
        uint64_t t2 = s0 + maj;
        memmove(v + 1, v, 7 * sizeof(v[0]));
        v[4] += t1;
        v[0] = t1 + t2;
    }
    for (int i = 0; i < 8; i++) h[i] += v[i];
}

void block(Ctx& c, const uint8_t* p) {
    switch (c.algo) {
        case Algo::SHA1: sha1Block(c.h32, p); break;
        case Algo::SHA256: sha256Block(c.h32, p); break;
        case Algo::SHA512: sha512Block(c.h64, p); break;
    }
}

void init(Ctx& c, Algo algo) {
    c.algo = algo;
    c.total = 0;
    c.fill = 0;
    switch (algo) {
        case Algo::SHA1:
            c.h32[0] = 0x67452301;
            c.h32[1] = 0xEFCDAB89;
            c.h32[2] = 0x98BADCFE;
            c.h32[3] = 0x10325476;
            c.h32[4] = 0xC3D2E1F0;
            break;
        case Algo::SHA256: memcpy(c.h32, kSha256Init, sizeof(kSha256Init)); break;
        case Algo::SHA512: memcpy(c.h64, kSha512Init, sizeof(kSha512Init)); break;
    }
}

void update(Ctx& c, const uint8_t* data, size_t len) {
    const size_t bs = blockSize(c.algo);
    c.total += len;
    while (len > 0) {
        size_t n = bs - c.fill;
        if (n > len) n = len;
        memcpy(c.buf + c.fill, data, n);
        c.fill += n;
        data += n;
        len -= n;
        if (c.fill == bs) {
            block(c, c.buf);
            c.fill = 0;
        }
    }
}

void finish(Ctx& c, uint8_t* out) {
    const size_t bs = blockSize(c.algo);
    const size_t lenBytes = bs / 8;  // width of the trailing bit-length field
    const uint64_t bits = c.total * 8;

    uint8_t pad[128 + 16] = {0x80};
    size_t padLen = bs - c.fill;
    if (padLen < 1 + lenBytes) padLen += bs;
    for (int i = 0; i < 8; i++) pad[padLen - 1 - i] = (uint8_t)(bits >> (8 * i));
    update(c, pad, padLen);

    const size_t n = digestSize(c.algo);
    if (c.algo == Algo::SHA512) {
        for (size_t i = 0; i < n; i++) out[i] = (uint8_t)(c.h64[i / 8] >> (56 - 8 * (i % 8)));
    } else {
        for (size_t i = 0; i < n; i++) out[i] = (uint8_t)(c.h32[i / 4] >> (24 - 8 * (i % 4)));
    }
    memset(&c, 0, sizeof(c));
}

}  // namespace

size_t digestSize(Algo algo) {
    switch (algo) {
        case Algo::SHA1: return 20;
        case Algo::SHA256: return 32;
        case Algo::SHA512: return 64;
    }
    return 0;
}

size_t hash(Algo algo, const uint8_t* msg, size_t len, uint8_t* out) {
    Ctx c;
    init(c, algo);
    update(c, msg, len);
    finish(c, out);
    return digestSize(algo);
}

size_t hmac(Algo algo, const uint8_t* key, size_t keyLen, const uint8_t* msg, size_t msgLen,
            uint8_t* out) {
    const size_t bs = blockSize(algo);
    const size_t ds = digestSize(algo);

    uint8_t k[128] = {0};
    if (keyLen > bs) {
        hash(algo, key, keyLen, k);
    } else {
        memcpy(k, key, keyLen);
    }

    uint8_t pad[128];
    uint8_t inner[kMaxDigest];
    Ctx c;

    for (size_t i = 0; i < bs; i++) pad[i] = k[i] ^ 0x36;
    init(c, algo);
    update(c, pad, bs);
    update(c, msg, msgLen);
    finish(c, inner);

    for (size_t i = 0; i < bs; i++) pad[i] = k[i] ^ 0x5c;
    init(c, algo);
    update(c, pad, bs);
    update(c, inner, ds);
    finish(c, out);

    memset(k, 0, sizeof(k));
    memset(pad, 0, sizeof(pad));
    memset(inner, 0, sizeof(inner));
    return ds;
}

bool equalConstTime(const uint8_t* a, const uint8_t* b, size_t len) {
    uint8_t diff = 0;
    for (size_t i = 0; i < len; i++) diff |= a[i] ^ b[i];
    return diff == 0;
}

}  // namespace otp
