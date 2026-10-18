# /// script
# requires-python = ">=3.13"
# dependencies = ["pillow>=13.0.0", "numpy>=2.5.4", "scipy>=1.18.1", "pydantic>=2.14.1"]
# ///
"""The translate-comic scripts: `pages <file>`, `write <work> <page>`, `cleanup <work> <keep>`."""

from __future__ import annotations

import os
import sys

from comic.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], os.environ, sys.stdin, sys.stdout))
