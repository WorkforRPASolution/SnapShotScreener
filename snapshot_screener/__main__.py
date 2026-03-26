"""Allow running as `python -m snapshot_screener`."""
import sys

from snapshot_screener.cli import main

sys.exit(main())
