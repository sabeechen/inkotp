// Setup mode. The device starts its own Wi-Fi network and serves the web UI on
// it; both the network password and the page's access code are random for each
// session and shown only on the device screen, so using the UI requires holding
// the device.
//
// The web API can add, replace and delete secrets but has no way to read them.
#pragma once

namespace portal {

// Runs a setup session and returns when the user leaves it or it times out.
void run();

}  // namespace portal
