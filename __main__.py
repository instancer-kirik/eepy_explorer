#!/usr/bin/env python3
"""
EPY Explorer - Main entry point
"""

import sys
import os

# Add src to Python path if running from directory
src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
if os.path.exists(src_path):
    sys.path.insert(0, src_path)

from eepy_explorer.src.app import main

if __name__ == "__main__":
    main() 