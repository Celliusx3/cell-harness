# 03 The preview's screenshot is one command in the PC

**Status.** open

**What to build.** The image adds one Debian program that writes the whole
screen as a PNG to stdout; pick the smallest that does. `services/desktop.py`
runs it through the engine instead of posting to port 7070, and keeps its PNG
check. `services/machine.py` drops `API_PORT` and the control token variable,
and the microsandbox engine stops publishing that port.

**Checks.** A unit test with a fake engine: the screenshot is the program's
stdout as a PNG, and output that is not a PNG raises `DesktopError`. Start the
app, open the computer's preview, and it shows the screen. The PC publishes
only the live-screen port.

**Blocked by.** 02
