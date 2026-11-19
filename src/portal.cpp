#include "portal.h"

#include <Arduino.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_random.h>

#include "board.h"
#include "clock.h"
#include "lock.h"
#include "otp.h"
#include "store.h"
#include "ui.h"
#include "version.h"

// web/index.html, linked in by board_build.embed_txtfiles.
extern const char kIndexStart[] asm("_binary_web_index_html_start");
extern const char kIndexEnd[] asm("_binary_web_index_html_end");
extern const char kDecoderStart[] asm("_binary_web_vendor_jsqr_min_js_start");
extern const char kDecoderEnd[] asm("_binary_web_vendor_jsqr_min_js_end");

namespace portal {
namespace {

constexpr uint32_t kIdleTimeoutMs = 10 * 60 * 1000;
constexpr int kMaxAuthFails = 10;
constexpr size_t kTokenLen = 8;
constexpr size_t kApPassLen = 12;

enum class View { JoinQr, JoinText, UrlQr, UrlText, PinConfirm };

WebServer server(80);
char apSsid[20];
char apPass[kApPassLen + 1];
char token[kTokenLen + 1];

uint32_t lastActivity;
int authFails;
bool done;
bool restartWhenDone;

// A PIN submitted from the web UI takes effect only once it has been entered
// correctly on the device, so a slip in the browser cannot lock the owner out.
char pendingPin[lock::kMaxLength + 1];
char enteredPin[lock::kMaxLength + 1];
const char* pinResult;  // reported to the web UI once

void randomText(char* out, size_t len) {
    // No look-alike characters: these get read off an e-ink screen.
    static const char kAlphabet[] = "abcdefghjkmnpqrstuvwxyz23456789";
    for (size_t i = 0; i < len; i++) out[i] = kAlphabet[esp_random() % (sizeof(kAlphabet) - 1)];
    out[len] = '\0';
}

void appendJsonString(String& json, const char* s) {
    json += '"';
    for (; *s; s++) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') {
            json += '\\';
            json += (char)c;
        } else if (c < 0x20) {
            char esc[8];
            snprintf(esc, sizeof(esc), "\\u%04x", c);
            json += esc;
        } else {
            json += (char)c;
        }
    }
    json += '"';
}

void sendOk() { server.send(200, "application/json", "{\"ok\":true}"); }

void sendError(const char* message, int status = 400) {
    String json = "{\"ok\":false,\"error\":";
    appendJsonString(json, message);
    json += '}';
    server.send(status, "application/json", json);
}

// Every API call must carry the code from the device screen.
bool authed() {
    const String& got = server.header("X-Auth");
    if (got.length() == kTokenLen &&
        otp::equalConstTime((const uint8_t*)got.c_str(), (const uint8_t*)token, kTokenLen)) {
        lastActivity = millis();
        return true;
    }
    if (++authFails >= kMaxAuthFails) done = true;
    sendError("Wrong code", 401);
    return false;
}

// Request lines go to the USB serial port to help diagnose setup problems.
// Nothing secret is in them: the access code travels in a header and account
// details in the request body.
void logRequest() {
    Serial.printf("setup: %s %s%s\n", server.method() == HTTP_GET ? "GET" : "POST",
                  server.hostHeader().c_str(), server.uri().c_str());
}

void handleIndex() {
    logRequest();
    server.sendHeader("Cache-Control", "no-store");
    server.send_P(200, "text/html", kIndexStart, kIndexEnd - kIndexStart - 1);
}

void handleDecoder() {
    logRequest();
    server.sendHeader("Cache-Control", "max-age=86400");
    server.send_P(200, "text/javascript", kDecoderStart, kDecoderEnd - kDecoderStart - 1);
}

void handleState() {
    if (!authed()) return;
    const store::Settings& st = store::settings();
    String json;
    json.reserve(2048);
    json += "{\"ok\":true,\"version\":\"" INKOTP_VERSION "\",\"battery\":";
    json += board::batteryPercent();
    json += ",\"maxAccounts\":";
    json += store::kMaxAccounts;

    json += ",\"time\":{\"valid\":";
    json += clk::valid() ? "true" : "false";
    json += ",\"now\":";
    json += (uint32_t)clk::now();
    json += ",\"lastSync\":";
    json += (uint32_t)clk::lastSync();
    json += '}';

    // Labels and parameters only. Secrets never leave the device.
    json += ",\"accounts\":[";
    bool first = true;
    for (int i = 0; i < store::count(); i++) {
        const int slot = store::slotAt(i);
        otp::Account a;
        if (!store::load(slot, a)) continue;
        if (!first) json += ',';
        first = false;
        json += "{\"id\":";
        json += slot;
        json += ",\"label\":";
        appendJsonString(json, a.label);
        json += ",\"algo\":\"";
        json += otp::algoName(a.algo);
        json += "\",\"digits\":";
        json += a.digits;
        json += ",\"period\":";
        json += a.period;
        json += '}';
        memset(&a, 0, sizeof(a));
    }

    json += "],\"nets\":[";
    for (int i = 0; i < store::netCount(); i++) {
        store::Net n;
        store::net(i, n);
        if (i) json += ',';
        appendJsonString(json, n.ssid);
        memset(&n, 0, sizeof(n));
    }

    json += "],\"pin\":{\"enabled\":";
    json += lock::enabled() ? "true" : "false";
    json += ",\"length\":";
    json += lock::length();
    json += ",\"pending\":";
    json += pendingPin[0] ? "true" : "false";
    if (pinResult) {
        json += ",\"result\":";
        appendJsonString(json, pinResult);
        pinResult = nullptr;
    }

    json += "},\"settings\":{\"sleepSecs\":";
    json += st.sleepSecs;
    json += ",\"unlockSecs\":";
    json += st.unlockSecs;
    json += ",\"maxTries\":";
    json += st.maxTries;
    json += ",\"autoSync\":";
    json += st.autoSync ? "true" : "false";
    json += ",\"compact\":";
    json += (st.flags & store::kCompact) ? "true" : "false";
    json += ",\"sounds\":";
    json += (st.flags & store::kSounds) ? "true" : "false";
    json += ",\"owner\":";
    appendJsonString(json, st.owner);
    json += "}}";
    server.send(200, "application/json", json);
}

void handleAccount() {
    if (!authed()) return;
    const bool isNew = server.arg("id").length() == 0;
    const int slot = isNew ? -1 : server.arg("id").toInt();
    if (!isNew && !store::used(slot)) return sendError("No such account");

    otp::Account account;
    const char* err = nullptr;
    const String& label = server.arg("label");
    if (server.arg("uri").length() > 0) {
        err = otp::accountFromUri(server.arg("uri").c_str(), account);
        // A typed name wins over the one in the link.
        if (!err && label.length() > 0) otp::setLabel(account, label.c_str());
    } else {
        otp::Algo algo;
        const int digits = server.arg("digits").toInt();
        const int period = server.arg("period").toInt();
        if (!otp::parseAlgo(server.arg("algo").c_str(), algo) ||
            !otp::validParams(algo, digits, period)) {
            return sendError("Unsupported algorithm, digits or period");
        }
        if (server.arg("secret").length() > 0) {
            err = otp::accountFromSecret(label.c_str(), server.arg("secret").c_str(), account);
        } else if (isNew) {
            err = "Secret is required";
        } else if (!store::load(slot, account)) {
            err = "Stored account is unreadable";
        } else {
            // Editing without a new secret keeps the stored one.
            otp::setLabel(account, label.c_str());
        }
        if (!err) {
            account.algo = algo;
            account.digits = (uint8_t)digits;
            account.period = (uint16_t)period;
        }
    }
    if (!err && !account.label[0]) err = "Name is required";

    if (!err) {
        if (isNew) {
            if (store::add(account) < 0) err = "The device is full";
        } else if (!store::save(slot, account)) {
            err = "Could not save";
        }
    }
    memset(&account, 0, sizeof(account));
    if (err) return sendError(err);
    sendOk();
}

void handleAccountDelete() {
    if (!authed()) return;
    store::remove(server.arg("id").toInt());
    sendOk();
}

void handleAccountMove() {
    if (!authed()) return;
    const int delta = server.arg("dir") == "up" ? -1 : 1;
    if (!store::move(server.arg("id").toInt(), delta)) return sendError("Cannot move that account");
    sendOk();
}

void handleWifi() {
    if (!authed()) return;
    if (!store::saveNet(server.arg("ssid").c_str(), server.arg("pass").c_str())) {
        return sendError("Could not save that network (name missing, too long, or list full)");
    }
    sendOk();
}

void handleWifiDelete() {
    if (!authed()) return;
    store::removeNet(server.arg("ssid").c_str());
    sendOk();
}

void applyTimezone() {
    if (server.arg("tz").length() == 0) return;
    long tz = server.arg("tz").toInt();
    if (tz >= -14 * 60 && tz <= 14 * 60) store::settings().tzMinutes = (int16_t)tz;
}

void handleTime() {
    if (!authed()) return;
    const uint64_t ms = strtoull(server.arg("ms").c_str(), nullptr, 10);
    const time_t secs = (time_t)(ms / 1000);
    if (secs < 1767225600) return sendError("That time is in the past");
    long moved = clk::set(secs, (uint16_t)(ms % 1000));
    if (labs(moved) > clk::kMaxSilentJump) lock::onClockJump();
    applyTimezone();
    store::saveSettings();
    sendOk();
}

void handleSettings() {
    if (!authed()) return;
    const long sleepSecs = server.arg("sleepSecs").toInt();
    const long maxTries = server.arg("maxTries").toInt();
    const uint64_t unlockSecs = strtoull(server.arg("unlockSecs").c_str(), nullptr, 10);
    const String& owner = server.arg("owner");
    if (sleepSecs < 15 || sleepSecs > 3600) return sendError("Sleep time must be 15 to 3600 s");
    if (maxTries < 3 || maxTries > 50) return sendError("Wrong tries must be 3 to 50");
    if (unlockSecs > lock::kUntilPowerLoss) return sendError("Unlock time is too long");
    if (owner.length() >= sizeof(store::Settings::owner)) return sendError("Text is too long");

    store::Settings& st = store::settings();
    st.sleepSecs = (uint16_t)sleepSecs;
    st.maxTries = (uint8_t)maxTries;
    st.unlockSecs = (uint32_t)unlockSecs;
    st.autoSync = server.arg("autoSync") == "1";
    st.flags = (server.arg("compact") == "1" ? store::kCompact : 0) |
               (server.arg("sounds") == "1" ? store::kSounds : 0);
    board::enableSounds(st.flags & store::kSounds);
    memset(st.owner, 0, sizeof(st.owner));
    for (size_t i = 0; i < owner.length(); i++) {
        char c = owner[i];
        st.owner[i] = (c >= 0x20 && c <= 0x7e) ? c : '?';
    }
    applyTimezone();
    store::saveSettings();
    sendOk();
}

void handlePin() {
    if (!authed()) return;
    const String& pattern = server.arg("pattern");
    if (pattern.length() == 0) {
        lock::set("");
        pendingPin[0] = '\0';
        return sendOk();
    }
    if (!lock::validPattern(pattern.c_str())) return sendError("PIN must be 4 to 16 presses");
    strcpy(pendingPin, pattern.c_str());
    enteredPin[0] = '\0';
    pinResult = nullptr;
    sendOk();
}

void handleWipe() {
    if (!authed()) return;
    if (server.arg("confirm") != "ERASE") return sendError("Not confirmed");
    store::wipeAll();
    sendOk();
    done = true;
    restartWhenDone = true;
}

constexpr char kTextHint[] = "Dial up/down: show as text";
constexpr char kQrHint[] = "Dial up/down: show QR code";

bool isJoin(View view) { return view == View::JoinQr || view == View::JoinText; }
bool isText(View view) { return view == View::JoinText || view == View::UrlText; }

void draw(View view) {
    switch (view) {
        case View::JoinQr: {
            char payload[80];
            snprintf(payload, sizeof(payload), "WIFI:T:WPA;S:%s;P:%s;;", apSsid, apPass);
            ui::qr("1  Join this Wi-Fi", payload, apSsid, kTextHint);
            break;
        }
        case View::JoinText:
            ui::typed("1  Join this Wi-Fi", apSsid, "password", apPass, kQrHint);
            break;
        case View::UrlQr: {
            char url[48];
            snprintf(url, sizeof(url), "http://%s/#%s", WiFi.softAPIP().toString().c_str(), token);
            ui::qr("2  Open this page", url, WiFi.softAPIP().toString().c_str(), kTextHint);
            break;
        }
        case View::UrlText:
            ui::typed("2  Open this page", WiFi.softAPIP().toString().c_str(), "access code", token,
                      kQrHint);
            break;
        case View::PinConfirm:
            ui::pinEntry("Confirm new PIN", (int)strlen(enteredPin), (int)strlen(pendingPin),
                         "Enter it here");
            break;
    }
}

// Returns true when confirmation has finished, either way.
bool pinConfirmKey(board::Key key) {
    if (key == board::Key::Power) {
        pinResult = "cancelled on the device";
    } else {
        size_t n = strlen(enteredPin);
        enteredPin[n] = lock::symbol(key);
        enteredPin[n + 1] = '\0';
        if (n + 1 < strlen(pendingPin)) return false;
        if (strcmp(enteredPin, pendingPin) == 0) {
            lock::set(pendingPin);
            pinResult = "confirmed";
        } else {
            pinResult = "the presses on the device did not match";
        }
    }
    memset(pendingPin, 0, sizeof(pendingPin));
    memset(enteredPin, 0, sizeof(enteredPin));
    return true;
}

}  // namespace

void run() {
    ui::message("Setup", "Starting Wi-Fi...");

    uint8_t mac[6];
    WiFi.persistent(false);
    WiFi.mode(WIFI_AP);
    WiFi.softAPmacAddress(mac);
    snprintf(apSsid, sizeof(apSsid), "InkOTP-%02X%02X", mac[4], mac[5]);
    // The radio is on by now, which is what makes esp_random() truly random.
    randomText(apPass, kApPassLen);
    randomText(token, kTokenLen);
    WiFi.softAP(apSsid, apPass, 1, 0, 1);

    static bool routesAdded = false;
    if (!routesAdded) {
        routesAdded = true;
        WiFi.onEvent([](arduino_event_id_t, arduino_event_info_t info) {
            Serial.printf("setup: gave out address %s\n",
                          IPAddress(info.wifi_ap_staipassigned.ip.addr).toString().c_str());
        }, ARDUINO_EVENT_WIFI_AP_STAIPASSIGNED);
        static const char* kHeaders[] = {"X-Auth"};
        server.collectHeaders(kHeaders, 1);
        server.on("/", HTTP_GET, handleIndex);
        server.on("/jsqr.js", HTTP_GET, handleDecoder);
        server.on("/api/state", HTTP_GET, handleState);
        server.on("/api/account", HTTP_POST, handleAccount);
        server.on("/api/account/delete", HTTP_POST, handleAccountDelete);
        server.on("/api/account/move", HTTP_POST, handleAccountMove);
        server.on("/api/wifi", HTTP_POST, handleWifi);
        server.on("/api/wifi/delete", HTTP_POST, handleWifiDelete);
        server.on("/api/time", HTTP_POST, handleTime);
        server.on("/api/settings", HTTP_POST, handleSettings);
        server.on("/api/pin", HTTP_POST, handlePin);
        server.on("/api/wipe", HTTP_POST, handleWipe);
        server.onNotFound([] {
            logRequest();
            sendError("Not found", 404);
        });
    }
    server.begin();

    lastActivity = millis();
    authFails = 0;
    done = false;
    restartWhenDone = false;
    pendingPin[0] = enteredPin[0] = '\0';
    pinResult = nullptr;

    View view = View::JoinQr;
    View shown = View::JoinQr;
    bool advanced = false;
    int stations = 0;
    Serial.printf("setup: network %s is up at %s\n", apSsid, WiFi.softAPIP().toString().c_str());
    draw(view);

    while (!done && millis() - lastActivity < kIdleTimeoutMs) {
        server.handleClient();
        board::Key key = board::readKey();
        bool redraw = false;

        if (WiFi.softAPgetStationNum() != stations) {
            stations = WiFi.softAPgetStationNum();
            Serial.printf("setup: %d device(s) joined\n", stations);
        }

        if (pendingPin[0]) {
            if (view != View::PinConfirm) {
                view = View::PinConfirm;
                redraw = true;
            }
            if (key != board::Key::None) {
                lastActivity = millis();
                if (pinConfirmKey(key)) view = View::UrlQr;
                redraw = true;
            }
        } else {
            if (view == View::PinConfirm) view = View::UrlQr;  // cancelled from the web UI
            if (key == board::Key::Press) {
                // Switch step, keeping to QR codes or text as the user chose.
                if (isJoin(view)) {
                    view = isText(view) ? View::UrlText : View::UrlQr;
                } else {
                    view = isText(view) ? View::JoinText : View::JoinQr;
                }
            } else if (key == board::Key::Up || key == board::Key::Down) {
                if (isJoin(view)) {
                    view = isText(view) ? View::JoinQr : View::JoinText;
                } else {
                    view = isText(view) ? View::UrlQr : View::UrlText;
                }
            } else if (key == board::Key::Top || key == board::Key::Power) {
                done = true;
            }
            // Move on to the page link as soon as a phone joins.
            if (!advanced && WiFi.softAPgetStationNum() > 0) {
                advanced = true;
                view = isText(view) ? View::UrlText : View::UrlQr;
            }
        }

        if (redraw || view != shown) {
            draw(view);
            shown = view;
        }
        delay(5);
    }

    server.stop();
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_OFF);
    memset(apPass, 0, sizeof(apPass));
    memset(token, 0, sizeof(token));
    memset(pendingPin, 0, sizeof(pendingPin));
    if (restartWhenDone) {
        ui::message("Erased", "Restarting...");
        delay(1500);
        ESP.restart();
    }
}

}  // namespace portal
