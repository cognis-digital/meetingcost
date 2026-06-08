"""Entry point so the package runs as ``python -m meetingcost``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
