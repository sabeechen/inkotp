// Persistent storage: accounts, settings and saved Wi-Fi networks, all in NVS.
#pragma once

#include <stdint.h>

#include "otp.h"

namespace store {

constexpr int kMaxAccounts = 24;
constexpr int kMaxNets = 6;

struct Settings {
    uint16_t sleepSecs;   // idle time before the device sleeps
    int16_t tzMinutes;    // offset from UTC, used only to display the time
    uint32_t unlockSecs;  // how long a PIN unlock lasts; see lock.h
    uint8_t maxTries;     // wrong PINs before everything is wiped
    bool autoSync;        // refresh the clock over Wi-Fi when it gets stale
    char owner[49];       // shown on the sleep screen, e.g. a phone number
    uint8_t flags;        // kCompact | kSounds
};
// Settings::flags bits.
constexpr uint8_t kCompact = 1;  // show several codes per screen
constexpr uint8_t kSounds = 2;   // click the buzzer on button presses
// Stored as a blob. `flags` took over a padding byte that was always written
// as zero, so settings saved by older firmware still load.
static_assert(sizeof(Settings) == 60, "Settings changed size: bump kSettingsVersion");

struct Net {
    char ssid[33];
    char pass[65];
};

void begin();

// Accounts live in numbered slots; a slot number is stable until deleted.
// The order they are shown in is kept separately and can be changed.
bool used(int slot);
int count();
// The slot shown n-th, or -1.
int slotAt(int n);
// Moves an account one place earlier (delta -1) or later (+1) in display order.
bool move(int slot, int delta);
bool load(int slot, otp::Account& out);
// Returns the new slot, or -1 when full.
int add(const otp::Account& account);
bool save(int slot, const otp::Account& account);
void remove(int slot);

Settings& settings();
void saveSettings();

int netCount();
bool net(int index, Net& out);
// Adds a network, or replaces the password of one with the same SSID.
bool saveNet(const char* ssid, const char* pass);
void removeNet(const char* ssid);

// Erases every stored value, including the PIN.
void wipeAll();

}  // namespace store
