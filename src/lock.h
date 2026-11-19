// Optional PIN lock. The PIN is a pattern of button presses, written as a
// string of 'U' (dial up), 'D' (dial down), 'P' (dial press) and 'T' (top
// button).
//
// The lock is enforced by the firmware only: it stops someone who picks the
// device up from reading codes, but it does not encrypt the stored secrets.
// See SECURITY.md.
#pragma once

#include <stdint.h>

#include "board.h"

namespace lock {

constexpr int kMinLength = 4;
constexpr int kMaxLength = 16;
// Settings::unlockSecs value meaning "stay unlocked until power is lost".
constexpr uint32_t kUntilPowerLoss = 0xFFFFFFFF;

enum class Result { Ok, Wrong, Wiped };

void begin();

bool enabled();
int length();
bool validPattern(const char* pattern);
// The pattern letter for a key, or 0 for keys that are not part of a PIN.
char symbol(board::Key key);

// True when no PIN is set, or a previous unlock is still in force.
bool unlocked();

// Checks a pattern. The attempt is recorded before it is checked, so cutting
// power cannot buy extra tries. After Settings::maxTries consecutive failures
// all stored data is erased and Wiped is returned.
Result attempt(const char* pattern);
int triesLeft();
// Seconds to make the user wait before the next try.
int penaltySecs();

// Sets a new PIN, or removes it when pattern is empty.
void set(const char* pattern);

// Ends the current unlock.
void relock();

// Called when the device is about to sleep: an "every wake" unlock ends here.
void onSleep();

// Called when the clock is changed by more than a small correction, which
// makes a timed unlock meaningless.
void onClockJump();

}  // namespace lock
