#include "net.h"

#include <Arduino.h>
#include <WiFi.h>
#include <esp_sntp.h>
#include <sys/time.h>

#include "clock.h"
#include "lock.h"
#include "store.h"

namespace net {
namespace {

constexpr uint32_t kConnectTimeoutMs = 15000;
constexpr uint32_t kNtpTimeoutMs = 10000;

volatile bool gotTime = false;
long pendingJump = 0;

void onTimeSync(timeval*) { gotTime = true; }

void radioOff() {
    esp_sntp_stop();
    WiFi.disconnect(true, true);
    WiFi.mode(WIFI_OFF);
}

// Picks the saved network with the strongest signal.
bool strongestSaved(store::Net& out) {
    int found = WiFi.scanNetworks();
    int bestRssi = -1000;
    bool any = false;
    for (int i = 0; i < found; i++) {
        for (int n = 0; n < store::netCount(); n++) {
            store::Net saved;
            store::net(n, saved);
            if (WiFi.SSID(i) == saved.ssid && WiFi.RSSI(i) > bestRssi) {
                bestRssi = WiFi.RSSI(i);
                out = saved;
                any = true;
            }
        }
    }
    WiFi.scanDelete();
    return any;
}

}  // namespace

Outcome syncTime(void (*progress)(const char*)) {
    auto say = [&](const char* text) {
        if (progress) progress(text);
    };
    if (store::netCount() == 0) return {Sync::NoSavedNetworks, 0};

    const bool wasValid = clk::valid();
    const time_t before = clk::now();
    const uint32_t beforeMs = millis();

    say("Looking for Wi-Fi");
    WiFi.persistent(false);
    WiFi.mode(WIFI_STA);
    store::Net target;
    if (!strongestSaved(target)) {
        radioOff();
        return {Sync::NoneInRange, 0};
    }

    say("Connecting");
    WiFi.begin(target.ssid, target.pass);
    memset(target.pass, 0, sizeof(target.pass));
    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < kConnectTimeoutMs) delay(100);
    if (WiFi.status() != WL_CONNECTED) {
        radioOff();
        return {Sync::ConnectFailed, 0};
    }

    say("Asking for the time");
    gotTime = false;
    sntp_set_time_sync_notification_cb(onTimeSync);
    configTime(0, 0, "pool.ntp.org", "time.cloudflare.com");
    start = millis();
    while (!gotTime && millis() - start < kNtpTimeoutMs) delay(50);

    // SNTP has already moved the system clock; work out by how much.
    timeval tv;
    gettimeofday(&tv, nullptr);
    radioOff();
    if (!gotTime) {
        clk::begin();
        return {Sync::NoAnswer, 0};
    }

    const time_t expected = before + (time_t)((millis() - beforeMs) / 1000);
    const long jump = wasValid ? (long)(tv.tv_sec - expected) : 0;
    if (labs(jump) > clk::kMaxSilentJump) {
        clk::begin();  // back to the RTC's time until the user decides
        pendingJump = jump;
        return {Sync::NeedsConfirm, jump};
    }

    gettimeofday(&tv, nullptr);
    clk::set(tv.tv_sec, (uint16_t)(tv.tv_usec / 1000));
    return {Sync::Ok, jump};
}

void applyPending() {
    clk::set(clk::now() + pendingJump);
    lock::onClockJump();
    pendingJump = 0;
}

}  // namespace net
