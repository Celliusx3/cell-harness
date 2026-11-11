# 02 An APK installs and opens, a tap and typing work, and memory is measured

**Status.** open

**What to build.** `mcp-servers/phone/experiment/drive` installs a sample APK
with `pm install`, opens it, taps a button, types into a field, and takes a
screenshot after each step. It reads the microVM's memory, idle and with the
app open. The figures go into the table in `docs/rakazo.md` §5, and the
results into `docs/specs/android-phone/experiment.md`.

**Checks.** Run `experiment/drive`. The screenshots show the app opened, the
button's effect and the typed text. The table has a row for Redroid in
microsandbox with both figures. Then stop: the person reads the results and
says go before ticket 03 starts.

**Blocked by.** 01
