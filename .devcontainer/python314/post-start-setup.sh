#!/bin/bash

# Delegate to the shared devcontainer runtime script to avoid per-version duplicates.
bash "$(dirname "$0")/../post-start-setup.sh"
