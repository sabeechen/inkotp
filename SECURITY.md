# Security model

InkOTP is a convenience device built on hobbyist hardware. It is not a
certified security token. This page says plainly what it protects against.

## What it is designed to resist

**Remote attackers.** The radio is off unless you start a setup session or a
clock sync. During a clock sync the device makes one outbound time request and
accepts no connections. Bluetooth is never started, and there is no
over-the-air update.

**Reading secrets through the setup page.** No API returns a secret or a Wi-Fi
password. The firmware has a base32 decoder and no encoder.

**Someone else using the setup page.** Setup runs on the device's own WPA2
network. The network password and the page's access code are random for each
session and appear only on the device screen, so you need the device in hand.
Ten wrong access codes end the session.

**Someone who picks the device up (with a PIN set).** Codes are hidden until
the PIN is entered. Wrong attempts are counted in flash before they are checked,
are delayed, and erase the device after a configurable number of failures.

**Wrong codes from a bad clock.** Codes are hidden if the clock chip reports
power loss, was never set, or reads earlier than its last sync. Internet time is
unauthenticated, so a sync that would move the clock by more than two minutes
must be confirmed on the device.

## What it does not resist

**Reading the flash chip.** Secrets are stored unencrypted in the ESP32's
flash. Anyone with the device and a USB cable can dump them. The PIN does not
change this: it is enforced by the firmware and is far too short to serve as an
encryption key.

You can raise the bar by enabling ESP32 flash encryption, which is a one-way
hardware setting and is not turned on by this firmware. On the ESP32 revision in
the Core Ink, flash encryption has published fault-injection attacks, so treat
it as protection against casual dumping only.

**A lost device, in general.** If you lose the device, assume the secrets on it
are compromised and re-enrol two-factor authentication on each account. Keep a
list of what is on it.

**Malicious firmware.** Anyone with physical access can flash different
firmware over USB. Secure boot is not enabled.

**A compromised phone or computer during setup.** Whatever you type into the
setup page is visible to the device you type it on.

**Eavesdropping inside the setup network.** The page is served over HTTP. The
link is encrypted by WPA2 with a random 12-character password, and only one
client may join, but there is no TLS.

## Good practice

- Keep a paper copy of your recovery codes and secrets somewhere safe. This
  device has a battery and can be lost.
- Set a PIN if you carry the device.
- Sync the clock every month or two; the code screen reminds you when it is
  overdue.

## Reporting a problem

Please open an issue, or contact the maintainer privately for anything you
think should not be public yet.
