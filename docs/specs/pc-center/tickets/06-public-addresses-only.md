# 06 The PC reaches only public addresses

**Status.** done

**What to build.** `MicrosandboxEngine` creates the PC with outgoing rules that
deny loopback, private networks, link-local and cloud metadata addresses. It
allows the Mac ports of the skills' host services. The rules are one function
from the host-service ports to the engine's rule list, with its own test.

**Checks.** On the PC, a `curl` to the app's API at the Mac's address, port
4896, is refused. `curl https://example.com` answers. `translate-comic`, a skill
with a host service, still works.

**Blocked by.** 04
