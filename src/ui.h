// Everything drawn on the 200x200 e-ink panel.
#pragma once

#include <stdint.h>
#include <time.h>

#include "otp.h"

namespace ui {

void begin();

// The next draw does a slow full refresh that removes e-ink ghosting.
void cleanNext();

// One account: name, current code, time bar and the code that follows it.
// warning is an optional short footer text.
void code(const otp::Account& account, int index, int total, time_t now, int batteryPercent,
          const char* warning);
// Redraws only the time bar of the code screen.
void codeBar(uint32_t secondsLeft, uint32_t period);

// The compact view: up to kCompactRows accounts on one screen, each with its
// name, current code and time bar.
constexpr int kCompactRows = 3;
struct CompactRow {
    const char* label;
    const char* code;  // already formatted for display
    uint32_t secondsLeft;
    uint32_t period;
};
void compact(const CompactRow* rows, int count, const char* warning);
// Redraws only the time bars of the compact view; label and code are ignored.
void compactBars(const CompactRow* rows, int count);

void menu(const char* title, const char* const* items, int count, int selected);

// A title and up to five lines of text; null lines are skipped.
void message(const char* title, const char* line1, const char* line2 = nullptr,
             const char* line3 = nullptr, const char* line4 = nullptr,
             const char* footer = nullptr);

// PIN prompt showing `entered` of `length` presses.
void pinEntry(const char* title, int entered, int length, const char* note);

void qr(const char* title, const char* payload, const char* line1, const char* line2);
// A short random string in large type, for typing into another device by hand.
void typed(const char* title, const char* line, const char* caption, const char* value,
           const char* footer);

// Left on the screen while the device sleeps, so it carries nothing sensitive.
void sleepScreen(const char* owner);

}  // namespace ui
