#include "lock.h"

#include <Arduino.h>
#include <Preferences.h>
#include <esp_random.h>
#include <string.h>

#include "clock.h"
#include "sha.h"
#include "store.h"

namespace lock {
namespace {

constexpr int kHashRounds = 2000;
constexpr uint32_t kRtcMagic = 0x1a2b0001;

struct PinRecord {
    uint8_t length;
    uint8_t salt[16];
    uint8_t hash[32];
};

// Survives deep sleep, lost when the battery is. Guarded by a magic value
// because RTC memory holds garbage after a cold boot.
RTC_DATA_ATTR uint32_t rtcMagic;
RTC_DATA_ATTR int64_t rtcUnlockedUntil;  // UTC seconds; -1 = until power loss
RTC_DATA_ATTR bool rtcSessionUnlocked;   // "every wake" unlock, cleared on sleep

PinRecord pin;
bool hasPin = false;
uint8_t fails = 0;

Preferences& prefs() {
    static Preferences p;
    static bool open = false;
    if (!open) open = p.begin("inkotp", false);
    return p;
}

void stretch(const char* pattern, const uint8_t* salt, uint8_t* out) {
    otp::hmac(otp::Algo::SHA256, salt, sizeof(pin.salt), (const uint8_t*)pattern, strlen(pattern),
              out);
    for (int i = 1; i < kHashRounds; i++) {
        uint8_t next[otp::kMaxDigest];
        otp::hmac(otp::Algo::SHA256, salt, sizeof(pin.salt), out, 32, next);
        memcpy(out, next, 32);
    }
}

void clearUnlock() {
    rtcUnlockedUntil = 0;
    rtcSessionUnlocked = false;
}

void setFails(uint8_t n) {
    fails = n;
    prefs().putUChar("pinFails", n);
}

}  // namespace

void begin() {
    if (rtcMagic != kRtcMagic) {
        rtcMagic = kRtcMagic;
        clearUnlock();
    }
    hasPin = prefs().getBytes("pin", &pin, sizeof(pin)) == sizeof(pin) &&
             pin.length >= kMinLength && pin.length <= kMaxLength;
    fails = prefs().getUChar("pinFails", 0);
}

bool enabled() { return hasPin; }

int length() { return hasPin ? pin.length : 0; }

bool validPattern(const char* pattern) {
    size_t n = strlen(pattern);
    if (n < (size_t)kMinLength || n > (size_t)kMaxLength) return false;
    return strspn(pattern, "UDPT") == n;
}

char symbol(board::Key key) {
    switch (key) {
        case board::Key::Up: return 'U';
        case board::Key::Down: return 'D';
        case board::Key::Press: return 'P';
        case board::Key::Top: return 'T';
        default: return '\0';
    }
}

bool unlocked() {
    if (!hasPin) return true;
    if (rtcSessionUnlocked) return true;
    if (rtcUnlockedUntil == -1) return true;
    return clk::valid() && clk::now() < (time_t)rtcUnlockedUntil;
}

int triesLeft() {
    int max = store::settings().maxTries;
    return fails >= max ? 0 : max - fails;
}

int penaltySecs() {
    if (fails < 3) return 0;
    int secs = 1 << (fails - 2);
    return secs > 30 ? 30 : secs;
}

Result attempt(const char* pattern) {
    if (!hasPin) return Result::Ok;
    setFails(fails + 1);

    uint8_t hash[32];
    stretch(pattern, pin.salt, hash);
    bool match = strlen(pattern) == pin.length && otp::equalConstTime(hash, pin.hash, 32);
    memset(hash, 0, sizeof(hash));

    if (!match) {
        if (triesLeft() > 0) return Result::Wrong;
        store::wipeAll();
        hasPin = false;
        fails = 0;
        clearUnlock();
        return Result::Wiped;
    }

    setFails(0);
    uint32_t secs = store::settings().unlockSecs;
    rtcSessionUnlocked = true;
    if (secs == kUntilPowerLoss) {
        rtcUnlockedUntil = -1;
    } else if (secs > 0 && clk::valid()) {
        rtcUnlockedUntil = (int64_t)clk::now() + secs;
    } else {
        rtcUnlockedUntil = 0;
    }
    return Result::Ok;
}

void set(const char* pattern) {
    if (!pattern[0]) {
        prefs().remove("pin");
        hasPin = false;
    } else {
        pin.length = (uint8_t)strlen(pattern);
        esp_fill_random(pin.salt, sizeof(pin.salt));
        stretch(pattern, pin.salt, pin.hash);
        prefs().putBytes("pin", &pin, sizeof(pin));
        hasPin = true;
        // Whoever set the PIN has just proved they know it.
        rtcSessionUnlocked = true;
    }
    setFails(0);
}

void relock() { clearUnlock(); }

void onSleep() { rtcSessionUnlocked = false; }

void onClockJump() { rtcUnlockedUntil = 0; }

}  // namespace lock
