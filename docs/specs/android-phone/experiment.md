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

## 02 An APK installs and opens, a tap and typing work, and memory is measured

- **Install.** Fossify Notes 13 from F-Droid, streamed into `pm install -S`
  over exec's stdin: "Success".
- **Open, type and tap.** `am start` opens it. `input tap` then `input text`
  writes "Hello from Cell Harness" into the note. `input tap` on the + button
  opens "Add a new note". A screenshot after each step shows the change.
- **Memory**, read by `msb metrics` after a minute's settle, in a 2 GiB microVM:

  | | In the guest | Held on the Mac |
  |---|---|---|
  | Idle, home screen | 0.76 GiB | 1.11 GiB |
  | The notes app open | 0.89 GiB | 0.44–1.28 GiB |

  The guest figure is steady across samples. The Mac's figure moves as macOS
  compresses and reclaims the VM's pages, so it is a range, not a cost.
- **Against the earlier No.** The PC is 0.6 GB. Redroid in a Lima VM measured
  0.8 / 1.25 GB, and the Play emulator 2.2–3.2 GB. One shared phone at about
  0.9 GiB fits on an 8 GB Mac beside the PC. A phone per bot still does not.

Found on the way: typing makes the notes app show an undo button where + was,
so a tap aimed by an earlier screenshot pressed undo. A bot has to take a
fresh screenshot before every tap.
