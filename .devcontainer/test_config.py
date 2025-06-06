#!/usr/bin/env python3
"""
Test script to verify Windows mounting works correctly.
"""
import sys
import os
from pathlib import Path

# Mock the input to select option 1 (Windows mounting)
import io
sys.stdin = io.StringIO('1\n')

# Set environment to avoid non-interactive detection
if 'CODESPACES' in os.environ:
    del os.environ['CODESPACES']

# Import and run the main function
sys.path.append(str(Path(__file__).parent))
import configure_azure_mount

# Run the main function
result = configure_azure_mount.main()
print(f"\nScript completed with exit code: {result}")
