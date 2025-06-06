#!/usr/bin/env python3
"""
Test the configure-azure-mount functionality
"""
import json
from pathlib import Path

# Test data setup
devcontainer_path = Path("devcontainer.json")
backup_path = Path("devcontainer.json.backup")

# Read current state
with open(devcontainer_path, 'r') as f:
    config = json.load(f)

print(f"Current mounts: {config.get('mounts', 'No mounts section')}")

# Simulate adding Windows mount
MOUNT_CONFIGS = {
    "windows": {
        "source": "${localEnv:USERPROFILE}/.azure",
        "target": "/home/vscode/.azure",
        "type": "bind"
    }
}

# Add Windows mount
if "mounts" not in config:
    config["mounts"] = []

config["mounts"].append(MOUNT_CONFIGS["windows"])

# Save test version
with open("test_devcontainer.json", 'w') as f:
    json.dump(config, f, indent=2)

print(f"Windows mount added. Check test_devcontainer.json")
print(f"Mount config: {MOUNT_CONFIGS['windows']}")
