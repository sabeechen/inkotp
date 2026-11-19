#include "board.h"

#include <M5Unified.h>
#include <driver/gpio.h>
#include <driver/rtc_io.h>
#include <esp_sleep.h>

namespace board {
namespace {

// The Core Ink runs from the battery only while this pin is high.
constexpr gpio_num_t kPowerHold = GPIO_NUM_12;
constexpr gpio_num_t kDialPress = GPIO_NUM_38;
constexpr gpio_num_t kPowerButton = GPIO_NUM_27;
constexpr uint8_t kBuzzer = 2;

// One sound is a few beeps: frequency, length, the silence after it, and
// loudness as a duty cycle in percent (50 is the loudest).
struct Beep {
    uint16_t hz;
    uint16_t ms;
    uint16_t gapMs;
    uint8_t duty;
};
// Tune the sounds here. The buzzer is loudest around 2.7 to 4 kHz.
constexpr Beep kClick[] = {{2000, 3, 0, 5}};
constexpr Beep kConfirm[] = {{3200, 25, 40, 50}, {4000, 25, 0, 50}};
constexpr Beep kError[] = {{1200, 90, 60, 50}, {1200, 90, 0, 50}};
constexpr uint8_t kPwmBits = 10;

bool soundsOn = false;

template <size_t N>
void beep(const Beep (&beeps)[N]) {
    if (!ledcAttach(kBuzzer, beeps[0].hz, kPwmBits)) return;
    for (const Beep& b : beeps) {
        ledcChangeFrequency(kBuzzer, b.hz, kPwmBits);
        ledcWrite(kBuzzer, ((1u << kPwmBits) - 1) * b.duty / 100);
        delay(b.ms);
        ledcWrite(kBuzzer, 0);
        delay(b.gapMs);
    }
    // Leave the pin low so no current flows through the buzzer when silent.
    ledcDetach(kBuzzer);
    pinMode(kBuzzer, OUTPUT);
    digitalWrite(kBuzzer, LOW);
}

}  // namespace

void begin() {
    auto cfg = M5.config();
    cfg.clear_display = false;  // keep the sleep screen until there is something to draw
    cfg.internal_spk = false;
    cfg.internal_mic = false;
    cfg.internal_imu = false;
    cfg.led_brightness = 0;
    M5.begin(cfg);

    // sleep() latched the power-hold pin; M5.begin() has driven it high again.
    gpio_hold_dis(kPowerHold);
    gpio_deep_sleep_hold_dis();
}

bool wokeFromSleep() { return esp_sleep_get_wakeup_cause() != ESP_SLEEP_WAKEUP_UNDEFINED; }

Key readKey() {
    M5.update();
    Key key = Key::None;
    if (M5.BtnA.wasPressed()) {
        key = Key::Up;
    } else if (M5.BtnC.wasPressed()) {
        key = Key::Down;
    } else if (M5.BtnB.wasPressed()) {
        key = Key::Press;
    } else if (M5.BtnEXT.wasPressed()) {
        key = Key::Top;
    } else if (M5.BtnPWR.wasPressed()) {
        key = Key::Power;
    }
    if (key != Key::None) play(Sound::Click);
    return key;
}

bool topHeld() {
    M5.update();
    return M5.BtnEXT.isPressed();
}

bool dialHeld() {
    M5.update();
    return M5.BtnB.isPressed();
}

void flushKeys() {
    for (int i = 0; i < 100; i++) {
        M5.update();
        if (!M5.BtnB.isPressed() && !M5.BtnPWR.isPressed()) break;
        delay(10);
    }
    M5.update();
}

int batteryPercent() { return M5.Power.getBatteryLevel(); }

void enableSounds(bool on) { soundsOn = on; }

void play(Sound sound) {
    if (!soundsOn) return;
    switch (sound) {
        case Sound::Click: beep(kClick); break;
        case Sound::Confirm: beep(kConfirm); break;
        case Sound::Error: beep(kError); break;
    }
}

void sleep() {
    M5.Display.waitDisplay();
    M5.Display.sleep();

    // A button still held down would wake the device straight away.
    for (int i = 0; i < 300; i++) {
        if (gpio_get_level(kDialPress) && gpio_get_level(kPowerButton)) break;
        delay(10);
    }

    // Classic ESP32 can only wake on "all of these pins low", so each button
    // gets its own wake source.
    esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);
    esp_sleep_enable_ext0_wakeup(kDialPress, 0);
    rtc_gpio_pullup_en(kPowerButton);
    rtc_gpio_pulldown_dis(kPowerButton);
    esp_sleep_enable_ext1_wakeup_io(1ULL << kPowerButton, ESP_EXT1_WAKEUP_ALL_LOW);

    gpio_hold_en(kPowerHold);
    gpio_deep_sleep_hold_en();
    esp_deep_sleep_start();
    for (;;) {}
}

}  // namespace board
