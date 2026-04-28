#!/usr/bin/env python3
"""Backward-compatible shim — delegates to yokonex.main.

Allows `python main.py server --tui` to keep working after the package
has been restructured under the yokonex/ namespace.
"""
from yokonex.main import main

if __name__ == "__main__":
    main()
