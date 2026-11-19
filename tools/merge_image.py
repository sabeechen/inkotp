"""PlatformIO build step: join the bootloader, partition table and firmware
into one file that can be written to an erased device at address 0.

Writes inkotp-<env>-full.bin beside firmware.bin in the build directory.
"""
Import("env")  # noqa: F821 - provided by PlatformIO


def merge(source, target, env):
    images = [str(i) for i in env.Flatten(env.get("FLASH_EXTRA_IMAGES", []))]
    images += ["$ESP32_APP_OFFSET", "$BUILD_DIR/${PROGNAME}.bin"]
    out = "$BUILD_DIR/inkotp-${PIOENV}-full.bin"
    # $OBJCOPY is the platform's own esptool.
    cmd = ['"$OBJCOPY"', "--chip", env.BoardConfig().get("build.mcu"),
           "merge-bin", "-o", '"%s"' % out] + ['"%s"' % i for i in images]
    return env.Execute(" ".join(cmd))


env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", merge)  # noqa: F821
