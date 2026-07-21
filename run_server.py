#!/usr/bin/env python3
"""Path-independent launcher for MCP clients.

Adds this file's directory to sys.path so `pixabay` imports work regardless of
the client's working directory, then starts the stdio server.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pixabay.server import main  # noqa: E402

if __name__ == "__main__":
    main()
