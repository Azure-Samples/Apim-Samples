#!/usr/bin/env python3
"""
Quick test script to verify shared module imports work correctly.
"""

import sys
import os
from pathlib import Path

# Add shared Python modules to path
project_root = Path(__file__).parent
shared_python_path = project_root / 'shared' / 'python'
sys.path.insert(0, str(shared_python_path))

print("Testing shared module imports...")
print(f"Project root: {project_root}")
print(f"Shared Python path: {shared_python_path}")
print(f"Path exists: {shared_python_path.exists()}")
print()

try:
    import utils
    print("✅ utils imported successfully")
except ImportError as e:
    print(f"❌ Failed to import utils: {e}")

try:
    import apimrequests
    print("✅ apimrequests imported successfully")
except ImportError as e:
    print(f"❌ Failed to import apimrequests: {e}")

try:
    import apimtypes
    print("✅ apimtypes imported successfully")
except ImportError as e:
    print(f"❌ Failed to import apimtypes: {e}")

try:
    import authfactory
    print("✅ authfactory imported successfully")
except ImportError as e:
    print(f"❌ Failed to import authfactory: {e}")

try:
    import users
    print("✅ users imported successfully")
except ImportError as e:
    print(f"❌ Failed to import users: {e}")

print()
print("Testing standard packages...")

try:
    import requests
    print(f"✅ requests {requests.__version__} imported successfully")
except ImportError as e:
    print(f"❌ Failed to import requests: {e}")

try:
    import pandas
    print(f"✅ pandas {pandas.__version__} imported successfully")
except ImportError as e:
    print(f"❌ Failed to import pandas: {e}")

print()
print("All import tests completed!")
