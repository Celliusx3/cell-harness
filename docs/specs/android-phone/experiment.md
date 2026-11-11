# The phone experiment

Run on an Apple M3 Max, 36 GB, macOS 26, with microsandbox 0.7.13.

## 01 Android boots in a microVM

- **Kernel.** libkrunfw at `56bf194`, Linux 6.12.113, with
  `mcp-servers/phone/kernel/config-android` appended. Built in Docker in about
  ten minutes; the dylib is 24 MB, the stock one 25 MB.
- **Stock kernel.** The launcher stops at once: "the kernel has no binderfs".
- **Our kernel.** `/proc/filesystems` lists `binder`. Redroid 13 reaches
  `sys.boot_completed=1` six seconds after the launch, in a 2 GB, 2 CPU microVM.
- **Screenshot.** `screencap -p`, run through `msb exec` and `nsenter` into
  Android's namespaces, gives a 720x1280 PNG of the home screen on the Mac.
- **Decision 7 is settled.** Android's commands reach its services from
  microsandbox's exec, so no adb is needed.

Found on the way:

- `MSB_HOME` must be short: microsandbox refuses a socket path of 104 bytes or more.
- A kernel tree cannot be unpacked on the Mac's case-insensitive disk, so the
  build runs on a Docker volume.
- Android's init re-executes itself as `/system/bin/init second_stage`, so the
  helper finds Android as the one child of `unshare`.
