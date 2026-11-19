// Core Ink hardware: buttons, battery and sleep.
#pragma once

#include <stdint.h>

namespace board {

enum class Key : uint8_t { None, Up, Down, Press, Top, Power };
// Click: a press registered. Confirm: a long press was recognised. Error: wrong PIN.
enum class Sound : uint8_t { Click, Confirm, Error };

void begin();

// True when this boot is a wake from sleep rather than a power-on or reset.
bool wokeFromSleep();

// Returns a key once per press, with a click if sounds are on. Call it often.
Key readKey();
bool topHeld();
bool dialHeld();

// Swallows a press that is still held from waking the device.
void flushKeys();

int batteryPercent();

// Sounds are off until enabled. They are short and block while they play.
void enableSounds(bool on);
void play(Sound sound);

// Turns the CPU off, leaving the screen as it is. The dial press or the side
// power button wakes the device, which then boots from scratch.
[[noreturn]] void sleep();

}  // namespace board
