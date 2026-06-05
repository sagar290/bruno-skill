#!/usr/bin/env python3
"""
Backward-compatible entry point.

Prefer the installed ``bruno-sync`` CLI, but fall back to running
the package directly when installed from source or as a submodule.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bruno_sync.cli import main

if __name__ == "__main__":
    main()