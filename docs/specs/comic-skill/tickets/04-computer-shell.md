# 04 The bot runs commands in its computer

**Status.** done

**What to build.** `mcp-servers/computer`: a model tool `shell(command, stdin?, cwd?)`. It runs the command detached (`docker exec -d` of a small runner) writing `out` and `exit` under `/home/rakazo/.shell/<id>/`, where the id is a hash of cwd, command and stdin. It waits up to 15 s and answers `{status: "done", exit_code, output}` or `{status: "running", seconds, output}` (output is the last 10,000 characters). The same call again attaches to the running job; a finished result is given once, then its folder is removed. The idle stop waits while a job runs.

**Checks.** Unit tests with the fake Docker: a slow command answers `running` with a growing `seconds`; the same call attaches with one `exec -d`; the result comes once; the idle stop skips a running job; a long output keeps its end.

**Blocked by.** 02, 03
