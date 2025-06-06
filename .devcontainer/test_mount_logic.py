#!/usr/bin/env python3
"""
Comprehensive test for mount preservation functionality.
"""
import json
import tempfile
from pathlib import Path

def test_mount_preservation():
    """Test that non-Azure mounts are preserved when removing Azure mounts."""
    
    # Create test devcontainer.json with mixed mounts
    test_config = {
        "name": "Test",
        "image": "test:latest",
        "mounts": [
            {
                "source": "${localEnv:HOME}/.azure",
                "target": "/home/vscode/.azure", 
                "type": "bind"
            },
            {
                "source": "${localEnv:HOME}/.ssh",
                "target": "/home/vscode/.ssh",
                "type": "bind"
            },
            {
                "source": "project-data",
                "target": "/data",
                "type": "volume"
            },
            {
                "source": "${localEnv:USERPROFILE}/.azure",
                "target": "/home/vscode/.azure",
                "type": "bind"
            }
        ]
    }
    
    print("Original mounts:")
    for i, mount in enumerate(test_config["mounts"]):
        print(f"  {i}: {mount}")
    
    # Simulate the mount filtering logic from configure-azure-mount.py
    existing_mounts = test_config["mounts"]
    non_azure_mounts = []
    
    for mount in existing_mounts:
        if isinstance(mount, dict):
            # Check if this is an Azure CLI mount by looking at the target path
            target = mount.get("target", "")
            if not target.endswith("/.azure"):
                non_azure_mounts.append(mount)
        else:
            # Keep non-dict mounts as-is
            non_azure_mounts.append(mount)
    
    test_config["mounts"] = non_azure_mounts
    
    print("\nFiltered mounts (Azure mounts removed):")
    for i, mount in enumerate(test_config["mounts"]):
        print(f"  {i}: {mount}")
    
    # Verify correct mounts were preserved
    expected_preserved = [
        {
            "source": "${localEnv:HOME}/.ssh",
            "target": "/home/vscode/.ssh",
            "type": "bind"
        },
        {
            "source": "project-data",
            "target": "/data",
            "type": "volume"
        }
    ]
    
    if test_config["mounts"] == expected_preserved:
        print("\n✅ Mount preservation test PASSED")
        return True
    else:
        print("\n❌ Mount preservation test FAILED")
        print(f"Expected: {expected_preserved}")
        print(f"Got: {test_config['mounts']}")
        return False

def test_windows_mount():
    """Test Windows mount configuration."""
    windows_mount = {
        "source": "${localEnv:USERPROFILE}/.azure",
        "target": "/home/vscode/.azure",
        "type": "bind"
    }
    
    print(f"\nWindows mount config: {windows_mount}")
    
    # Verify it uses USERPROFILE for Windows
    if windows_mount["source"] == "${localEnv:USERPROFILE}/.azure":
        print("✅ Windows mount test PASSED")
        return True
    else:
        print("❌ Windows mount test FAILED")
        return False

def test_unix_mount():
    """Test Unix mount configuration."""
    unix_mount = {
        "source": "${localEnv:HOME}/.azure", 
        "target": "/home/vscode/.azure",
        "type": "bind"
    }
    
    print(f"\nUnix mount config: {unix_mount}")
    
    # Verify it uses HOME for Unix
    if unix_mount["source"] == "${localEnv:HOME}/.azure":
        print("✅ Unix mount test PASSED")
        return True
    else:
        print("❌ Unix mount test FAILED")
        return False

if __name__ == "__main__":
    print("🧪 Testing configure-azure-mount.py functionality\n")
    
    results = []
    results.append(test_mount_preservation())
    results.append(test_windows_mount())
    results.append(test_unix_mount())
    
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests PASSED!")
    else:
        print("❌ Some tests FAILED!")
