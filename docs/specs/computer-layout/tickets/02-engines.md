# 02 Each engine moves into engines/

**Status.** done

**What to build.** `engine.py` keeps only the `Engine` protocol. `DockerEngine`
and `DockerCli` move to `engines/docker.py`, and `docker.py` is deleted.
`microsandbox_engine.py` and `microsandbox_sdk.py` move to
`engines/microsandbox.py` and `engines/microsandbox_sdk.py`. Update every
import.

**Checks.** The suite passes 568. Breaking one docker argument and one
microsandbox call each makes a test fail.

**Blocked by.** 01
