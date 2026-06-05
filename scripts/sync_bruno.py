#!/usr/bin/env python3
"""
Backward-compatible entry point.

Run directly: python3 scripts/sync_bruno.py sync
Or install locally (pip install -e .) and use: bruno-sync sync
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bruno_sync.cli import main

if __name__ == "__main__":
    main()