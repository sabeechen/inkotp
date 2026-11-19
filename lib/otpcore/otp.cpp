#include "otp.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace otp {

int base32Decode(const char* text, uint8_t* out, size_t outSize) {
    uint32_t buffer = 0;
    int bits = 0;
    size_t n = 0;
    for (const char* p = text; *p; p++) {
        char ch = *p;
        if (ch == ' ' || ch == '-' || ch == '=' || ch == '\t' || ch == '\r' || ch == '\n') continue;
        int value;
        if (ch >= 'A' && ch <= 'Z') {
            value = ch - 'A';
        } else if (ch >= 'a' && ch <= 'z') {
            value = ch - 'a';
        } else if (ch >= '2' && ch <= '7') {
            value = ch - '2' + 26;
        } else {
            return -1;
        }
        buffer = (buffer << 5) | (uint32_t)value;
        bits += 5;
        if (bits >= 8) {
            if (n >= outSize) return -1;
            bits -= 8;
            out[n++] = (uint8_t)(buffer >> bits);
        }
    }
    return (int)n;
}

uint32_t hotp(Algo algo, const uint8_t* key, size_t keyLen, uint64_t counter, uint8_t digits) {
    uint8_t msg[8];
    for (int i = 7; i >= 0; i--) {
        msg[i] = (uint8_t)counter;
        counter >>= 8;
    }
    uint8_t mac[kMaxDigest];
    size_t macLen = hmac(algo, key, keyLen, msg, sizeof(msg), mac);

    // Dynamic truncation, RFC 4226 section 5.3.
    size_t offset = mac[macLen - 1] & 0x0f;
    uint32_t bin = (uint32_t)(mac[offset] & 0x7f) << 24 | (uint32_t)mac[offset + 1] << 16 |
                   (uint32_t)mac[offset + 2] << 8 | mac[offset + 3];
    memset(mac, 0, sizeof(mac));

    uint32_t mod = 1;
    for (int i = 0; i < digits; i++) mod *= 10;
    return bin % mod;
}

uint32_t totp(const Account& a, uint64_t unixTime) {
    return hotp(a.algo, a.secret, a.secretLen, unixTime / a.period, a.digits);
}

uint32_t secondsLeft(const Account& a, uint64_t unixTime) {
    return a.period - (uint32_t)(unixTime % a.period);
}

void formatCode(uint32_t code, uint8_t digits, char* out) {
    if (digits > 8) digits = 8;
    char plain[8];
    for (int i = digits - 1; i >= 0; i--) {
        plain[i] = (char)('0' + code % 10);
        code /= 10;
    }
    const int split = (digits + 1) / 2;
    int n = 0;
    for (int i = 0; i < digits; i++) {
        if (i == split) out[n++] = ' ';
        out[n++] = plain[i];
    }
    out[n] = '\0';
}

bool validParams(Algo algo, int digits, int period) {
    return (uint8_t)algo <= (uint8_t)Algo::SHA512 && digits >= 6 && digits <= 8 && period >= 5 &&
           period <= 300;
}

bool parseAlgo(const char* name, Algo& out) {
    char up[8] = {0};
    for (size_t i = 0; i < sizeof(up) - 1 && name[i]; i++) {
        up[i] = (char)toupper((unsigned char)name[i]);
    }
    if (!strcmp(up, "SHA1")) {
        out = Algo::SHA1;
    } else if (!strcmp(up, "SHA256")) {
        out = Algo::SHA256;
    } else if (!strcmp(up, "SHA512")) {
        out = Algo::SHA512;
    } else {
        return false;
    }
    return true;
}

const char* algoName(Algo algo) {
    switch (algo) {
        case Algo::SHA1: return "SHA1";
        case Algo::SHA256: return "SHA256";
        case Algo::SHA512: return "SHA512";
    }
    return "?";
}

namespace {

// strlcpy is not portable; this truncates the same way.
void copyTrunc(char* dst, size_t dstSize, const char* src) {
    size_t n = strlen(src);
    if (n >= dstSize) n = dstSize - 1;
    memcpy(dst, src, n);
    dst[n] = '\0';
}

const char* setSecret(Account& a, const char* base32Secret) {
    int n = base32Decode(base32Secret, a.secret, sizeof(a.secret));
    if (n < 0) return "Secret is not valid base32, or is too long";
    if (n < (int)kMinSecret) return "Secret is too short";
    a.secretLen = (uint8_t)n;
    return nullptr;
}

int hexValue(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    c = (char)tolower((unsigned char)c);
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

// Percent-decodes [begin, end) into out, truncating to outSize - 1.
void urlDecode(const char* begin, const char* end, char* out, size_t outSize) {
    size_t n = 0;
    for (const char* p = begin; p < end && n + 1 < outSize; p++) {
        if (*p == '%' && end - p >= 3 && hexValue(p[1]) >= 0 && hexValue(p[2]) >= 0) {
            out[n++] = (char)(hexValue(p[1]) << 4 | hexValue(p[2]));
            p += 2;
        } else {
            out[n++] = *p;
        }
    }
    out[n] = '\0';
}

void setDefaults(Account& a) {
    memset(&a, 0, sizeof(a));
    a.algo = Algo::SHA1;
    a.digits = 6;
    a.period = 30;
}

}  // namespace

void setLabel(Account& a, const char* label) {
    while (*label == ' ') label++;
    size_t n = strlen(label);
    while (n > 0 && label[n - 1] == ' ') n--;
    if (n > kMaxLabel) n = kMaxLabel;
    memcpy(a.label, label, n);
    a.label[n] = '\0';
    // Keep labels to printable ASCII; the device font has nothing else.
    for (size_t i = 0; i < n; i++) {
        if ((unsigned char)a.label[i] < 0x20 || (unsigned char)a.label[i] > 0x7e) a.label[i] = '?';
    }
}

const char* accountFromSecret(const char* label, const char* base32Secret, Account& out) {
    setDefaults(out);
    setLabel(out, label);
    if (!out.label[0]) return "Name is required";
    return setSecret(out, base32Secret);
}

const char* accountFromUri(const char* uri, Account& out) {
    static const char kPrefix[] = "otpauth://";
    while (*uri == ' ') uri++;
    if (strncmp(uri, kPrefix, sizeof(kPrefix) - 1) != 0) return "Not an otpauth:// link";
    const char* type = uri + sizeof(kPrefix) - 1;
    if (strncmp(type, "totp/", 5) != 0) return "Only time-based (totp) links are supported";

    const char* path = type + 5;
    const char* query = strchr(path, '?');
    if (!query) return "Link has no secret";

    setDefaults(out);

    char pathLabel[96];
    urlDecode(path, query, pathLabel, sizeof(pathLabel));

    char issuer[48] = "";
    char secret[160] = "";
    int digits = out.digits;
    int period = out.period;
    for (const char* p = query + 1; *p;) {
        const char* end = strchr(p, '&');
        if (!end) end = p + strlen(p);
        const char* eq = (const char*)memchr(p, '=', (size_t)(end - p));
        if (eq) {
            char key[12];
            char value[160];
            urlDecode(p, eq, key, sizeof(key));
            urlDecode(eq + 1, end, value, sizeof(value));
            if (!strcmp(key, "secret")) {
                memcpy(secret, value, sizeof(secret));
            } else if (!strcmp(key, "issuer")) {
                copyTrunc(issuer, sizeof(issuer), value);
            } else if (!strcmp(key, "algorithm")) {
                if (!parseAlgo(value, out.algo)) return "Unsupported algorithm";
            } else if (!strcmp(key, "digits")) {
                digits = atoi(value);
            } else if (!strcmp(key, "period")) {
                period = atoi(value);
            }
            memset(value, 0, sizeof(value));
        }
        p = *end ? end + 1 : end;
    }

    const char* err = nullptr;
    if (!validParams(out.algo, digits, period)) {
        err = "Unsupported digits or period";
    } else if (!secret[0]) {
        err = "Link has no secret";
    } else {
        err = setSecret(out, secret);
    }
    memset(secret, 0, sizeof(secret));
    if (err) return err;
    out.digits = (uint8_t)digits;
    out.period = (uint16_t)period;

    // The path is usually "Issuer:account"; add the issuer when it is missing.
    char label[160] = "";
    if (issuer[0] && strncmp(pathLabel, issuer, strlen(issuer)) != 0) {
        copyTrunc(label, sizeof(label), issuer);
        copyTrunc(label + strlen(label), sizeof(label) - strlen(label), ": ");
    }
    copyTrunc(label + strlen(label), sizeof(label) - strlen(label), pathLabel);
    setLabel(out, label);
    if (!out.label[0]) setLabel(out, "Account");
    return nullptr;
}

}  // namespace otp
