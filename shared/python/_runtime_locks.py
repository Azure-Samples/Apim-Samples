"""Stable synchronization shared by Azure command execution and console output.

Autoreload: reload_unsafe
Restart the kernel after editing this module. Replacing an active lock would
allow existing and reloaded callers to enter the same critical section together.
"""

import threading

AZ_CLI_LOCK = threading.Lock()
PRINT_LOCK = threading.Lock()
