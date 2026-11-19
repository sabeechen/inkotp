// Host tests for lib/otpcore. Run with: pio test -e native
#include <stdio.h>
#include <string.h>
#include <unity.h>

#include "otp.h"

using namespace otp;

void setUp() {}
void tearDown() {}

static void expectHex(const char* expected, const uint8_t* got, size_t len) {
    char hex[2 * kMaxDigest + 1];
    for (size_t i = 0; i < len; i++) snprintf(hex + 2 * i, 3, "%02x", got[i]);
    TEST_ASSERT_EQUAL_STRING(expected, hex);
}

static void test_digests() {
    uint8_t out[kMaxDigest];
    const uint8_t* abc = (const uint8_t*)"abc";
    expectHex("a9993e364706816aba3e25717850c26c9cd0d89d", out, hash(Algo::SHA1, abc, 3, out));
    expectHex("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", out,
              hash(Algo::SHA256, abc, 3, out));
    expectHex("ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
              "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
              out, hash(Algo::SHA512, abc, 3, out));
    // Empty input and an input that spills the length into a second block.
    expectHex("da39a3ee5e6b4b0d3255bfef95601890afd80709", out, hash(Algo::SHA1, abc, 0, out));
    const char* two = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    expectHex("248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1", out,
              hash(Algo::SHA256, (const uint8_t*)two, strlen(two), out));
}

// RFC 4231 test case 6: a key longer than the block size is hashed first.
static void test_hmac_long_key() {
    uint8_t key[131];
    memset(key, 0xaa, sizeof(key));
    const char* msg = "Test Using Larger Than Block-Size Key - Hash Key First";
    uint8_t out[kMaxDigest];
    size_t n = hmac(Algo::SHA256, key, sizeof(key), (const uint8_t*)msg, strlen(msg), out);
    expectHex("60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54", out, n);
}

static void test_base32() {
    uint8_t out[32];
    TEST_ASSERT_EQUAL(20, base32Decode("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", out, sizeof(out)));
    TEST_ASSERT_EQUAL_MEMORY("12345678901234567890", out, 20);
    TEST_ASSERT_EQUAL(20, base32Decode("gezd gnbv-gy3t qojq gezd gnbv gy3t qojq==", out, sizeof(out)));
    TEST_ASSERT_EQUAL_MEMORY("12345678901234567890", out, 20);
    TEST_ASSERT_EQUAL(-1, base32Decode("GEZD1NBV", out, sizeof(out)));  // '1' is not base32
    TEST_ASSERT_EQUAL(-1, base32Decode("GEZDGNBVGY3TQOJQ", out, 4));    // does not fit
}

// RFC 4226 appendix D.
static void test_hotp() {
    const uint8_t* key = (const uint8_t*)"12345678901234567890";
    const uint32_t expected[] = {755224, 287082, 359152, 969429, 338314,
                                 254676, 287922, 162583, 399871, 520489};
    for (uint64_t i = 0; i < 10; i++) {
        TEST_ASSERT_EQUAL_UINT32(expected[i], hotp(Algo::SHA1, key, 20, i, 6));
    }
}

// RFC 6238 appendix B.
static void test_totp() {
    struct Vector {
        uint64_t time;
        uint32_t sha1, sha256, sha512;
    };
    const Vector vectors[] = {
        {59ULL, 94287082, 46119246, 90693936},
        {1111111109ULL, 7081804, 68084774, 25091201},
        {1111111111ULL, 14050471, 67062674, 99943326},
        {1234567890ULL, 89005924, 91819424, 93441116},
        {2000000000ULL, 69279037, 90698825, 38618901},
        {20000000000ULL, 65353130, 77737706, 47863826},
    };
    const char* seed = "1234567890123456789012345678901234567890123456789012345678901234";
    Account a = {};
    a.digits = 8;
    a.period = 30;
    memcpy(a.secret, seed, 64);
    for (const Vector& v : vectors) {
        a.algo = Algo::SHA1;
        a.secretLen = 20;
        TEST_ASSERT_EQUAL_UINT32(v.sha1, totp(a, v.time));
        a.algo = Algo::SHA256;
        a.secretLen = 32;
        TEST_ASSERT_EQUAL_UINT32(v.sha256, totp(a, v.time));
        a.algo = Algo::SHA512;
        a.secretLen = 64;
        TEST_ASSERT_EQUAL_UINT32(v.sha512, totp(a, v.time));
    }
    TEST_ASSERT_EQUAL_UINT32(1, secondsLeft(a, 59));
    TEST_ASSERT_EQUAL_UINT32(30, secondsLeft(a, 60));
}

static void test_format() {
    char out[10];
    formatCode(7081804, 8, out);
    TEST_ASSERT_EQUAL_STRING("0708 1804", out);
    formatCode(42, 6, out);
    TEST_ASSERT_EQUAL_STRING("000 042", out);
    formatCode(1234567, 7, out);
    TEST_ASSERT_EQUAL_STRING("1234 567", out);
}

static void test_from_secret() {
    Account a;
    TEST_ASSERT_NULL(accountFromSecret("  GitHub ", "JBSWY3DPEHPK3PXP", a));
    TEST_ASSERT_EQUAL_STRING("GitHub", a.label);
    TEST_ASSERT_EQUAL(10, a.secretLen);
    TEST_ASSERT_EQUAL(6, a.digits);
    TEST_ASSERT_EQUAL(30, a.period);
    TEST_ASSERT_NOT_NULL(accountFromSecret("", "JBSWY3DPEHPK3PXP", a));
    TEST_ASSERT_NOT_NULL(accountFromSecret("x", "JBSWY3DP", a));  // too short
    TEST_ASSERT_NOT_NULL(accountFromSecret("x", "not base32!", a));
}

static void test_from_uri() {
    Account a;
    TEST_ASSERT_NULL(accountFromUri(
        "otpauth://totp/Example:alice@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Example", a));
    TEST_ASSERT_EQUAL_STRING("Example:alice@example.com", a.label);
    TEST_ASSERT_EQUAL(Algo::SHA1, a.algo);

    TEST_ASSERT_NULL(accountFromUri(
        "otpauth://totp/alice%40example.com?issuer=ACME%20Co&algorithm=sha256&digits=8&period=60"
        "&secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ",
        a));
    TEST_ASSERT_EQUAL_STRING("ACME Co: alice@example.com", a.label);
    TEST_ASSERT_EQUAL(Algo::SHA256, a.algo);
    TEST_ASSERT_EQUAL(8, a.digits);
    TEST_ASSERT_EQUAL(60, a.period);
    TEST_ASSERT_EQUAL(20, a.secretLen);

    TEST_ASSERT_NOT_NULL(accountFromUri("otpauth://hotp/x?secret=JBSWY3DPEHPK3PXP&counter=1", a));
    TEST_ASSERT_NOT_NULL(accountFromUri("otpauth://totp/x?issuer=y", a));
    TEST_ASSERT_NOT_NULL(accountFromUri("otpauth://totp/x?secret=JBSWY3DPEHPK3PXP&digits=10", a));
    TEST_ASSERT_NOT_NULL(accountFromUri("https://example.com", a));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_digests);
    RUN_TEST(test_hmac_long_key);
    RUN_TEST(test_base32);
    RUN_TEST(test_hotp);
    RUN_TEST(test_totp);
    RUN_TEST(test_format);
    RUN_TEST(test_from_secret);
    RUN_TEST(test_from_uri);
    return UNITY_END();
}
