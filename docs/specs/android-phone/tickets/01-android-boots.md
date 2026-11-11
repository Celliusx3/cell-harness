# 01 Android boots in a microVM on this Mac

**Status.** open

**What to build.** `mcp-servers/phone/kernel/config-android`, a kernel config
fragment that turns on binder and binderfs. `mcp-servers/phone/kernel/build`
rebuilds microsandbox's libkrunfw fork at the revision microsandbox 0.7.13
pins, with that fragment, into `libkrunfw.5.dylib`.
`mcp-servers/phone/experiment/boot` starts the Redroid arm64 image in a
microsandbox microVM with `MSB_LIBKRUNFW_PATH` set to that build.

**Checks.** On an Apple Silicon Mac, run `experiment/boot`. Inside the microVM,
`getprop sys.boot_completed` prints `1` within two minutes. `screencap -p` run
through microsandbox's exec writes a PNG of the home screen to the Mac. The
result notes whether exec reached Android's services, which settles spec
decision 6.

**Blocked by.** none
