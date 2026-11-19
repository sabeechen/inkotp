// SHA-1, SHA-256, SHA-512 and HMAC. Self-contained so the same code runs on
// the device and in the host tests.
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace otp {

enum class Algo : uint8_t { SHA1 = 0, SHA256 = 1, SHA512 = 2 };

constexpr size_t kMaxDigest = 64;

size_t digestSize(Algo algo);

// Both write digestSize(algo) bytes to out and return that length.
size_t hash(Algo algo, const uint8_t* msg, size_t len, uint8_t* out);
size_t hmac(Algo algo, const uint8_t* key, size_t keyLen, const uint8_t* msg, size_t msgLen,
            uint8_t* out);

// Constant-time comparison for secrets and their hashes.
bool equalConstTime(const uint8_t* a, const uint8_t* b, size_t len);

}  // namespace otp
