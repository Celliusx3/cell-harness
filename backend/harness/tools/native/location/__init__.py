"""`get_location` — where the person is, from their device.

The first client tool, and the one that shaped the spine in `tools/client/`:
this package is only the declaration and the datum. How the call waits, how
the browser or a chat answers it, and what the model reads on each outcome
are the spine's — see [docs/client-data.md](../../../../../docs/client-data.md).
"""

from harness.tools.native.location.models import Location
from harness.tools.native.location.tool import LOCATION, LOCATION_TOOL

__all__ = ["LOCATION", "LOCATION_TOOL", "Location"]
