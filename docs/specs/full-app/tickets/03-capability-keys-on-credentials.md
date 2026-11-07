# 03 Capability keys are added on the Credentials page

**Status.** open

**What to build.** A credential type "Capability key": you pick a capability
and one of the keys it needs, and paste the value. It is sealed in the
keyring like the other credentials and shows only its last four characters.
Saving, changing or deleting one restarts that capability through 02's
call. The Add credential dialog lists only capabilities that need a key.

**Checks.** On a private copy of the app: Places is off, and Credentials
offers "Places: GOOGLE_MAPS_API_KEY". Save a key, and within a minute a
bot finds a place, with no restart. Delete it, and Places is off again.
Backend and frontend tests cover the type and the restart.

**Blocked by.** 02
