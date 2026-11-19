// TOTP (RFC 6238) code generation, base32 decoding and otpauth:// parsing.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "sha.h"

namespace otp {

constexpr size_t kMaxLabel = 32;
constexpr size_t kMaxSecret = 64;
constexpr size_t kMinSecret = 10;  // 80 bits, the shortest secret in common use

struct Account {
    char label[kMaxLabel + 1];
    uint8_t secret[kMaxSecret];
    uint8_t secretLen;
    Algo algo;
    uint8_t digits;   // 6 to 8
    uint16_t period;  // seconds
};

// Decodes RFC 4648 base32. Case-insensitive; spaces, dashes and '=' padding
// are skipped. Returns the decoded length, or -1 if the text is malformed or
// does not fit. There is deliberately no encoder: nothing in the firmware can
// turn a stored secret back into text.
int base32Decode(const char* text, uint8_t* out, size_t outSize);

uint32_t hotp(Algo algo, const uint8_t* key, size_t keyLen, uint64_t counter, uint8_t digits);

uint32_t totp(const Account& account, uint64_t unixTime);

// Seconds until the code for unixTime expires (1..period).
uint32_t secondsLeft(const Account& account, uint64_t unixTime);

// Zero-padded decimal, grouped for reading: "123 456" or "1234 5678".
// out needs 10 bytes.
void formatCode(uint32_t code, uint8_t digits, char* out);

bool validParams(Algo algo, int digits, int period);
bool parseAlgo(const char* name, Algo& out);
const char* algoName(Algo algo);

// Stores a trimmed, printable-ASCII copy of label, truncated to kMaxLabel.
void setLabel(Account& account, const char* label);

// Fills label, algo, digits and period with defaults, then decodes the secret.
// Returns nullptr on success or a message suitable for showing to the user.
const char* accountFromSecret(const char* label, const char* base32Secret, Account& out);

// Parses an otpauth://totp/... URI. Same return convention as above.
const char* accountFromUri(const char* uri, Account& out);

}  // namespace otp
