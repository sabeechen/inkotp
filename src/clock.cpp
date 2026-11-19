#include "clock.h"

#include <M5Unified.h>
#include <Preferences.h>
#include <sys/time.h>

namespace clk {
namespace {

// No real time is earlier than this (2026-01-01); anything below means the RTC
// was never set.
constexpr time_t kEarliest = 1767225600;

bool isValid = false;
time_t syncedAt = 0;

// Days since 1970-01-01 for a proleptic Gregorian date.
int64_t daysFromCivil(int y, int m, int d) {
    y -= m <= 2;
    const int64_t era = (y >= 0 ? y : y - 399) / 400;
    const int yoe = (int)(y - era * 400);
    const int doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    const int doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + doe - 719468;
}

bool readRtc(time_t& out) {
    m5::rtc_datetime_t dt;
    if (!M5.Rtc.isEnabled() || !M5.Rtc.getDateTime(&dt)) return false;
    out = (time_t)(daysFromCivil(dt.date.year, dt.date.month, dt.date.date) * 86400 +
                   dt.time.hours * 3600 + dt.time.minutes * 60 + dt.time.seconds);
    return true;
}

void setSystem(time_t utc) {
    timeval tv = {utc, 0};
    settimeofday(&tv, nullptr);
}

void storeSync(time_t utc) {
    Preferences p;
    p.begin("inkotp", false);
    p.putULong64("lastSync", (uint64_t)utc);
    p.end();
    syncedAt = utc;
}

}  // namespace

void begin() {
    Preferences p;
    p.begin("inkotp", true);
    syncedAt = (time_t)p.getULong64("lastSync", 0);
    p.end();

    time_t rtc = 0;
    isValid = readRtc(rtc) && !M5.Rtc.getVoltLow() && rtc >= kEarliest && syncedAt != 0 &&
              rtc >= syncedAt;
    if (isValid) setSystem(rtc);
}

bool valid() { return isValid; }

time_t now() { return time(nullptr); }

long set(time_t utc, uint16_t millis) {
    if (millis > 0) {
        delay(1000 - millis % 1000);
        utc += 1;
    }
    long moved = isValid ? (long)(utc - now()) : 0;

    tm parts;
    gmtime_r(&utc, &parts);
    M5.Rtc.setDateTime(&parts);
    setSystem(utc);
    storeSync(utc);
    isValid = utc >= kEarliest;
    return moved;
}

time_t lastSync() { return syncedAt; }

long syncAge() { return syncedAt ? (long)(now() - syncedAt) : -1; }

}  // namespace clk
