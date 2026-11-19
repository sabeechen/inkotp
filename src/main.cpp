// InkOTP: an offline TOTP token for the M5Stack Core Ink.
//
// The device boots from scratch on every wake, shows codes, and goes back to
// sleep. Each screen below is a function that runs until the user leaves it
// and returns the screen to show next.
#include <Arduino.h>

#include "board.h"
#include "clock.h"
#include "lock.h"
#include "net.h"
#include "otp.h"
#include "portal.h"
#include "store.h"
#include "ui.h"
#include "version.h"

namespace {

using board::Key;

enum class Screen { Codes, Menu, Status, Sync, Setup, Sleep };

constexpr uint32_t kRtcMagic = 0x1a2b0002;
constexpr int64_t kAutoSyncRetrySecs = 24 * 3600;
constexpr int kLowBatteryPercent = 15;

// Kept across sleep; garbage after a cold boot, hence the magic value.
RTC_DATA_ATTR uint32_t rtcMagic;
RTC_DATA_ATTR int rtcAccountIndex;      // the account last on screen
RTC_DATA_ATTR int64_t rtcLastAutoSync;  // when an automatic sync was last tried

Screen screen = Screen::Codes;
uint32_t lastActivity;

void touch() { lastActivity = millis(); }

bool idle() { return millis() - lastActivity > store::settings().sleepSecs * 1000UL; }

// Blocks until a key is pressed. Returns Key::None when the idle time runs out.
Key waitKey() {
    for (;;) {
        Key key = board::readKey();
        if (key != Key::None) {
            touch();
            return key;
        }
        if (idle()) return Key::None;
        delay(10);
    }
}

void formatDuration(long secs, char* out, size_t size) {
    secs = labs(secs);
    if (secs < 120) {
        snprintf(out, size, "%ld s", secs);
    } else if (secs < 7200) {
        snprintf(out, size, "%ld min", secs / 60);
    } else if (secs < 172800) {
        snprintf(out, size, "%ld h", secs / 3600);
    } else {
        snprintf(out, size, "%ld days", secs / 86400);
    }
}

// Refreshes a stale clock on the way to sleep, where the delay bothers nobody.
void maybeAutoSync() {
    if (!store::settings().autoSync || store::netCount() == 0 || !clk::valid()) return;
    if (clk::syncAge() < clk::kStaleSecs) return;
    const int64_t now = clk::now();
    if (rtcLastAutoSync != 0 && now - rtcLastAutoSync < kAutoSyncRetrySecs) return;
    rtcLastAutoSync = now;
    ui::message("Clock", "Checking the time...");
    // A large jump needs the user's say-so; left alone here, it will be offered
    // the next time they sync by hand.
    net::syncTime();
}

[[noreturn]] void goToSleep() {
    lock::onSleep();
    maybeAutoSync();
    ui::sleepScreen(store::settings().owner);
    board::sleep();
}

[[noreturn]] void restartAfter(const char* title, const char* line1, const char* line2) {
    ui::message(title, line1, line2);
    delay(4000);
    ESP.restart();
    for (;;) {}
}

// Returns once the device is unlocked. Sleeps on the side button or when idle.
void requireUnlock() {
    if (lock::unlocked()) return;
    char entered[lock::kMaxLength + 1] = "";
    char note[32] = "";
    for (;;) {
        ui::pinEntry("Enter PIN", (int)strlen(entered), lock::length(), note[0] ? note : nullptr);
        Key key = waitKey();
        if (key == Key::None || key == Key::Power) goToSleep();

        size_t n = strlen(entered);
        entered[n] = lock::symbol(key);
        entered[n + 1] = '\0';
        if ((int)n + 1 < lock::length()) continue;

        // Checking takes a moment; show the last press so it does not look stuck.
        ui::pinEntry("Enter PIN", lock::length(), lock::length(), "Checking...");
        lock::Result result = lock::attempt(entered);
        memset(entered, 0, sizeof(entered));
        if (result == lock::Result::Ok) return;
        if (result == lock::Result::Wiped) {
            restartAfter("Erased", "Too many wrong PINs.", "Everything was removed.");
        }
        board::play(board::Sound::Error);
        int wait = lock::penaltySecs();
        if (wait > 0) {
            snprintf(note, sizeof(note), "Wrong. Wait %d s", wait);
            ui::pinEntry("Enter PIN", 0, lock::length(), note);
            delay(wait * 1000UL);
            board::flushKeys();
            touch();
        }
        snprintf(note, sizeof(note), "Wrong. %d tries left", lock::triesLeft());
    }
}

// Offered when the top button is held during power-on. Works without the PIN,
// which is the way out for someone who has forgotten it.
void offerFactoryReset() {
    ui::message("Erase device?", "Keep holding the", "top button for", "5 seconds.");
    for (int i = 0; i < 50; i++) {
        if (!board::topHeld()) return;
        delay(100);
    }
    ui::message("Erase device?", "Press the dial to", "erase everything.", nullptr, nullptr,
                "Any other button: cancel");
    board::flushKeys();
    while (board::topHeld()) delay(10);
    touch();
    if (waitKey() != Key::Press) return;
    store::wipeAll();
    restartAfter("Erased", "Restarting...", nullptr);
}

const char* codeWarning(int battery) {
    if (battery >= 0 && battery < kLowBatteryPercent) return "low battery";
    if (clk::syncAge() > clk::kWarnSecs) return "sync clock";
    return nullptr;
}

// Shown in place of codes when there is nothing trustworthy to show.
Screen notice(const char* title, const char* line1, const char* line2, const char* line3) {
    ui::message(title, line1, line2, line3, nullptr, "Press: menu");
    Key key = waitKey();
    return key == Key::None || key == Key::Top || key == Key::Power ? Screen::Sleep : Screen::Menu;
}

// Holding the dial in for this long on the code screen sleeps the device.
constexpr uint32_t kLongPressMs = 700;

// Call right after a dial press: true if it turns out to be a long one.
bool isLongPress() {
    const uint32_t start = millis();
    while (board::dialHeld()) {
        if (millis() - start >= kLongPressMs) {
            board::play(board::Sound::Confirm);
            return true;
        }
        delay(10);
    }
    return false;
}

// How many steps the time bar moves in over one period.
constexpr uint32_t kBarSteps = 10;

Screen runCodes() {
    if (!clk::valid()) {
        return notice("Clock not set", "Codes are hidden", "until the clock", "has been set.");
    }
    const int total = store::count();
    if (total == 0) {
        return notice("No accounts", "Choose Setup in", "the menu to add", "your accounts.");
    }
    if (rtcAccountIndex < 0 || rtcAccountIndex >= total) rtcAccountIndex = 0;

    // The standard view is a page of one account; the compact view shows several.
    const bool compact = store::settings().flags & store::kCompact;
    const int perPage = compact ? ui::kCompactRows : 1;

    for (;;) {
        const int first = rtcAccountIndex / perPage * perPage;
        const int shown = total - first < perPage ? total - first : perPage;
        otp::Account accounts[ui::kCompactRows];
        for (int i = 0; i < shown; i++) {
            if (!store::load(store::slotAt(first + i), accounts[i])) {
                memset(accounts, 0, sizeof(accounts));
                return notice("Storage error", "An account could", "not be read.", nullptr);
            }
        }

        time_t now = clk::now();
        const int battery = board::batteryPercent();
        char codes[ui::kCompactRows][10];
        ui::CompactRow rows[ui::kCompactRows];
        uint64_t steps[ui::kCompactRows];
        uint32_t ticks[ui::kCompactRows];
        for (int i = 0; i < shown; i++) {
            const otp::Account& a = accounts[i];
            otp::formatCode(otp::totp(a, (uint64_t)now), a.digits, codes[i]);
            rows[i] = {a.label, codes[i], otp::secondsLeft(a, (uint64_t)now), a.period};
            steps[i] = (uint64_t)now / a.period;
            ticks[i] = rows[i].secondsLeft * kBarSteps / a.period;
        }
        if (compact) {
            ui::compact(rows, shown, codeWarning(battery));
        } else {
            ui::code(accounts[0], first, total, now, battery, codeWarning(battery));
        }

        Screen next = Screen::Codes;
        for (;;) {
            Key key = board::readKey();
            if (key != Key::None) touch();
            if (key == Key::Up) {
                rtcAccountIndex = first > 0 ? first - perPage : (total - 1) / perPage * perPage;
                break;
            }
            if (key == Key::Down) {
                rtcAccountIndex = first + perPage < total ? first + perPage : 0;
                break;
            }
            if (key == Key::Press) next = isLongPress() ? Screen::Sleep : Screen::Menu;
            if (key == Key::Top || key == Key::Power || idle()) next = Screen::Sleep;
            if (next != Screen::Codes) break;

            now = clk::now();
            bool rolledOver = false, barMoved = false;
            for (int i = 0; i < shown; i++) {
                const otp::Account& a = accounts[i];
                if ((uint64_t)now / a.period != steps[i]) rolledOver = true;
                rows[i].secondsLeft = otp::secondsLeft(a, (uint64_t)now);
                const uint32_t tick = rows[i].secondsLeft * kBarSteps / a.period;
                if (tick != ticks[i]) barMoved = true;
                ticks[i] = tick;
            }
            if (rolledOver) break;  // a code has changed: redraw the page
            if (barMoved) {
                if (compact) {
                    ui::compactBars(rows, shown);
                } else {
                    ui::codeBar(rows[0].secondsLeft, rows[0].period);
                }
            }
            delay(20);
        }
        memset(accounts, 0, sizeof(accounts));
        memset(codes, 0, sizeof(codes));
        if (next != Screen::Codes) return next;
    }
}

Screen runMenu() {
    static int selected = 0;
    const char* items[6];
    Screen targets[6];
    int count = 0;
    auto add = [&](const char* label, Screen target) {
        items[count] = label;
        targets[count++] = target;
    };
    add("Codes", Screen::Codes);
    add("Sync clock", Screen::Sync);
    add("Setup", Screen::Setup);
    add("Status", Screen::Status);
    const int lockItem = lock::enabled() ? count : -1;
    if (lockItem >= 0) add("Lock now", Screen::Sleep);
    add("Sleep", Screen::Sleep);
    if (selected >= count) selected = 0;

    for (;;) {
        ui::menu("InkOTP", items, count, selected);
        switch (waitKey()) {
            case Key::Up: selected = (selected + count - 1) % count; break;
            case Key::Down: selected = (selected + 1) % count; break;
            case Key::Press:
                if (selected == lockItem) lock::relock();
                return targets[selected];
            case Key::Top: return Screen::Codes;
            default: return Screen::Sleep;
        }
    }
}

Screen runStatus() {
    char when[24], synced[28], power[20], about[28], age[12];
    if (clk::valid()) {
        time_t local = clk::now() + store::settings().tzMinutes * 60;
        tm parts;
        gmtime_r(&local, &parts);
        strftime(when, sizeof(when), "%a %d %b  %H:%M", &parts);
        formatDuration(clk::syncAge(), age, sizeof(age));
        snprintf(synced, sizeof(synced), "Clock set %s ago", age);
    } else {
        snprintf(when, sizeof(when), "Clock not set");
        synced[0] = '\0';
    }
    snprintf(power, sizeof(power), "Battery %d%%", board::batteryPercent());
    snprintf(about, sizeof(about), "%d accounts   v%s", store::count(), INKOTP_VERSION);
    ui::message("Status", when, synced[0] ? synced : nullptr, power, about, "Any button: back");
    return waitKey() == Key::None ? Screen::Sleep : Screen::Menu;
}

Screen runSync() {
    net::Outcome outcome = net::syncTime([](const char* stage) { ui::message("Sync clock", stage); });
    char amount[12], line[28];
    formatDuration(outcome.jumpSecs, amount, sizeof(amount));
    switch (outcome.result) {
        case net::Sync::Ok:
            snprintf(line, sizeof(line), "It was %s off.", amount);
            ui::message("Sync clock", "Clock updated.", outcome.jumpSecs ? line : nullptr);
            break;
        case net::Sync::NoSavedNetworks:
            ui::message("Sync clock", "No saved Wi-Fi.", "Add a network", "in Setup.");
            break;
        case net::Sync::NoneInRange:
            ui::message("Sync clock", "No saved Wi-Fi", "network is in range.");
            break;
        case net::Sync::ConnectFailed:
            ui::message("Sync clock", "Could not join", "the network.");
            break;
        case net::Sync::NoAnswer:
            ui::message("Sync clock", "No answer from", "the time server.");
            break;
        case net::Sync::NeedsConfirm:
            snprintf(line, sizeof(line), "is %s %s.", amount, outcome.jumpSecs > 0 ? "behind" : "ahead");
            ui::message("Check this", "The network says", "this clock", line, "Change it?",
                        "Press: yes    Top: no");
            touch();
            if (waitKey() == Key::Press) {
                net::applyPending();
                ui::message("Sync clock", "Clock updated.");
            } else {
                ui::message("Sync clock", "Clock left as it was.");
            }
            break;
    }
    touch();
    return waitKey() == Key::None ? Screen::Sleep : Screen::Menu;
}

Screen runSetup() {
    portal::run();
    ui::cleanNext();
    touch();
    return Screen::Codes;
}

}  // namespace

void setup() {
    board::begin();
    ui::begin();
    store::begin();
    clk::begin();
    board::enableSounds(store::settings().flags & store::kSounds);
    lock::begin();
    if (rtcMagic != kRtcMagic) {
        rtcMagic = kRtcMagic;
        rtcAccountIndex = 0;
        rtcLastAutoSync = 0;
    }

    if (!board::wokeFromSleep() && board::topHeld()) offerFactoryReset();
    board::flushKeys();
    touch();
    requireUnlock();
}

void loop() {
    switch (screen) {
        case Screen::Codes: screen = runCodes(); break;
        case Screen::Menu: screen = runMenu(); break;
        case Screen::Status: screen = runStatus(); break;
        case Screen::Sync: screen = runSync(); break;
        case Screen::Setup: screen = runSetup(); break;
        case Screen::Sleep: goToSleep();
    }
}
