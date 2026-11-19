// Timekeeping. The battery-backed RTC chip holds UTC; the system clock is
// loaded from it at every boot and used while awake.
#pragma once

#include <stdint.h>
#include <time.h>

namespace clk {

// A sync that would move the clock further than this needs confirming.
constexpr long kMaxSilentJump = 120;
// Age at which the clock is called stale and an automatic sync is attempted.
constexpr long kStaleSecs = 7L * 24 * 3600;
// Age at which the code screen warns that codes may be drifting.
constexpr long kWarnSecs = 45L * 24 * 3600;

// Loads the system clock from the RTC and decides whether it can be trusted.
void begin();

// False until the clock has been set, and again if the RTC lost power or went
// backwards. Codes must never be shown while this is false.
bool valid();

time_t now();

// Sets the RTC and system clock to utc (waiting for a second boundary when
// millis is non-zero) and records the sync. Returns how far the clock moved in
// seconds, or 0 if it was not valid before.
long set(time_t utc, uint16_t millis = 0);

// When the clock was last set, or 0.
time_t lastSync();

// Seconds since the last sync, or -1 if never.
long syncAge();

}  // namespace clk
