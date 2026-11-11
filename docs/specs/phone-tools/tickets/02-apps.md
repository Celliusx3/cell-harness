# 02 A bot manages the phone's apps

**Status.** done

**What to build.** `list_apps` (third-party packages), `foreground_app`,
`terminate_app(package)` (force-stop), `uninstall_app(package)` and
`clear_app_data(package)` in `mcp-servers/phone/`, through `pm`, `am` and
`dumpsys`. The droidVNC-NG package cannot be uninstalled or cleared: it is the
person's screen.

**Checks.** An integration test pins each command and the refusal for
droidVNC-NG. On the real phone, `list_apps` names Pinduoduo, and
`foreground_app` names it while it is open.

**Blocked by.** none
