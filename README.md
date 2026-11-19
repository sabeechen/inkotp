# InkOTP

Firmware that turns an [M5Stack Core Ink](https://docs.m5stack.com/en/core/coreink)
into a small, self-contained TOTP token: an e-ink screen that shows your
one-time codes, with no phone, app or cloud service involved.

It is meant as a backup authenticator for a handful of critical accounts.

> **Status: early.** Version 0.1.0 runs on a Core Ink and its code-generation
> logic passes the RFC test vectors. It has had one user and no outside review.

## What it does

- Shows TOTP codes (SHA-1, SHA-256, SHA-512; 6 to 8 digits; any period), with
  the next code alongside the current one, or three accounts to a screen in
  the optional compact view.
- Keeps time with the Core Ink's battery-backed clock chip, and refuses to show
  codes whenever that clock cannot be trusted.
- Sleeps with a static screen and wakes on a button press.
- Is configured from a phone or computer through a web page the device serves
  on its own short-lived Wi-Fi network.
- Optionally locks behind a PIN made of button presses.
- Optionally clicks its buzzer when a button press registers.

## Design rules

- **Secrets are write-only.** The web UI can add, replace and delete secrets.
  No interface returns one, and the firmware contains no base32 encoder.
- **The radio is normally off.** It is on only during a setup session you start
  from the menu, and for the few seconds of a clock sync.
- **No server dependency.** The clock can always be set from a browser during
  setup; internet time is a convenience.
- **Updates by USB only.** There is no over-the-air update code or partition.

See [SECURITY.md](SECURITY.md) for what this does and does not protect against.

## Controls

| Control | Action |
|---|---|
| Dial up / down | Previous / next account (or page, in compact view), or move in a menu |
| Dial press | Wake; open the menu; select |
| Dial long press | Sleep, from the code screen |
| Top button | Back; sleep from the code screen |
| Side button | Wake; sleep |

Menu: **Codes**, **Sync clock**, **Setup**, **Status**, **Lock now** (when a PIN
is set), **Sleep**.

## First-time setup

1. Wake the device and choose **Setup** from the menu.
2. Scan the first QR code with your phone to join the device's Wi-Fi network.
   Your phone may warn that the network has no internet; stay connected.
   Turn off any VPN on the phone first, or the setup page will not load.
3. Press the dial to show the second QR code and scan it to open the setup page.
4. Press **Set clock from this browser**, then add your accounts. Either
   photograph the QR code a service shows you (or choose a saved image of it),
   or paste the secret key or the whole `otpauth://` link.
5. Optionally save a Wi-Fi network for automatic clock sync, and set a PIN.
   The same page reorders accounts and holds the other settings: compact
   view, button sounds, the idle time before sleep and a line of text for the
   sleep screen.
6. Press the top button on the device to leave setup.

If you cannot scan, turn the dial up or down on either QR code to show the same
details in large type: the network name and password, then the page address
(`192.168.4.1`) and the access code.

To erase the device without the PIN, hold the top button while switching it on
and follow the prompts.

## Installing a release

Each [release](https://github.com/sabeechen/inkotp/releases) carries two
files, built by GitHub Actions from the tagged source. Flash them over USB
with [esptool](https://docs.espressif.com/projects/esptool/) (`pip install
esptool`), or from Chrome or Edge with Espressif's
[browser flasher](https://espressif.github.io/esptool-js/).

A first install, which **erases any accounts and settings on the device**:

```sh
esptool --chip esp32 write-flash 0x0 inkotp-coreink-0.1.0-full.bin
```

An update to a device that already runs InkOTP, which keeps them:

```sh
esptool --chip esp32 write-flash 0x10000 inkotp-coreink-0.1.0-update.bin
```

## Building

Requires [PlatformIO](https://platformio.org/).

```sh
pio run                # build
pio run -t upload      # flash over USB
pio test -e native     # run the host tests
```

On Linux you may need to be in the `dialout` group to flash.

To work on the web UI without a device:

```sh
python3 tools/mock_device.py
```

## Layout

| Path | Contents |
|---|---|
| `lib/otpcore/` | Hashing, HMAC, TOTP and `otpauth://` parsing. No hardware dependencies. |
| `src/` | Firmware: screens, storage, clock, PIN lock, clock sync, setup portal. |
| `web/index.html` | The setup page, embedded in the firmware image. |
| `web/vendor/` | [jsQR](https://github.com/cozmo/jsQR) 1.4.0 (Apache-2.0), which reads QR codes from photos in the browser. |
| `test/` | Host tests for `lib/otpcore`. |
| `tools/` | Constant-table generator, the mock device and the build step that makes the single-file image. |
| `hardware/` | An unbuilt draft of a thinner custom board and a printed case. The firmware does not support it yet; see `hardware/README.md`. |

## Limitations

- QR codes are read from a photo, not a live camera view: browsers only allow
  live camera access over HTTPS, which the device does not serve.
- Export codes from authenticator apps (`otpauth-migration://`) are not
  supported.
- Account names are limited to 32 printable ASCII characters.
- Up to 24 accounts and 6 Wi-Fi networks.
- The setup page is served over plain HTTP, protected by the Wi-Fi network's
  own encryption. See SECURITY.md.

## Licence

InkOTP is released into the public domain under the [Unlicense](UNLICENSE).

The bundled QR decoder in `web/vendor/` is a separate work under the
Apache License 2.0; see `web/vendor/jsqr.LICENSE`. Firmware built from this
repository also links M5Unified and M5GFX (MIT) and the Arduino-ESP32 core.
