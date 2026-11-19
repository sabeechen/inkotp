// Clock sync over Wi-Fi. The radio is on only inside syncTime(): the device
// joins a saved network, asks an NTP server for the time and disconnects. It
// never listens for connections on someone else's network.
#pragma once

namespace net {

enum class Sync {
    Ok,
    NoSavedNetworks,
    NoneInRange,
    ConnectFailed,
    NoAnswer,
    // The answer is far from the current clock. Network time is not
    // authenticated, so the caller must ask the user before applying it.
    NeedsConfirm,
};

struct Outcome {
    Sync result;
    long jumpSecs;  // how far the clock moved, or would move
};

// progress, if given, is called with a short status text at each stage.
Outcome syncTime(void (*progress)(const char*) = nullptr);

// Resolve a NeedsConfirm outcome.
void applyPending();

}  // namespace net
