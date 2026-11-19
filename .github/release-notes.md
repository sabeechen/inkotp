Firmware for the M5Stack Core Ink.

| File | Use it for | Write it at |
|---|---|---|
| `inkotp-coreink-*-full.bin` | A first install. **Erases any accounts and settings already on the device.** | `0x0` |
| `inkotp-coreink-*-update.bin` | Updating a device that already runs InkOTP. Keeps accounts and settings. | `0x10000` |

See "Installing a release" in the README for the commands. `SHA256SUMS` lists
the checksums of both files.
