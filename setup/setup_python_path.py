#!/usr/bin/env python3

"""
Cross-platform PYTHONPATH setup for APIM Samples.

This script automatically detects the project root and configures PYTHONPATH
to include shared Python modules. Cross-platform compatibility is achieved by:
- Using pathlib.Path for all file operations (handles Windows/Unix path separators)
- Using absolute paths (eliminates relative path issues across platforms)
- Using UTF-8 encoding explicitly (ensures consistent file encoding)
- Using Python's sys.path for runtime PYTHONPATH configuration
"""

import sys
from pathlib import Path  # Cross-platform path handling (Windows: \, Unix: /)


def get_project_root() -> Path:
    """
    Get the absolute path to the project root directory.
    
    Cross-platform strategy:
    - Uses pathlib.Path for consistent path operations across OS
    - Searches upward from script location to find project indicators
    - Returns absolute paths that work on Windows, macOS, and Linux
    
    Returns:
        Path: Absolute path to project root directory
    """
    # Start from script's parent directory (since we're in setup/ folder)
    # Path(__file__).resolve() gives absolute path, .parent.parent goes up two levels
    start_path = Path(__file__).resolve().parent.parent
    
    # Project root indicators - files that should exist at project root
    # These help identify the correct directory regardless of where script is run
    indicators = ['README.md', 'requirements.txt', 'bicepconfig.json']
    current_path = start_path
    
    # Walk up the directory tree until we find all indicators or reach filesystem root
    while current_path != current_path.parent:  # Stop at filesystem root
        # Check if all indicator files exist in current directory
        if all((current_path / indicator).exists() for indicator in indicators):
            return current_path
        current_path = current_path.parent
    
    # Fallback: if indicators not found, assume parent of script directory is project root
    # This handles cases where the project structure might be different
    return Path(__file__).resolve().parent.parent


def setup_python_path() -> None:
    """
    Add shared Python modules to PYTHONPATH for runtime import resolution.
    
    This modifies sys.path in the current Python session to enable imports
    from the shared/python directory. Cross-platform compatibility:
    - Uses pathlib for path construction (handles OS-specific separators)
    - Converts to string only when needed for sys.path compatibility
    - Uses sys.path.insert(0, ...) to prioritize our modules
    """
    project_root = get_project_root()
    # Use pathlib's / operator for cross-platform path joining
    shared_python_path = project_root / 'shared' / 'python'
    
    if shared_python_path.exists():
        # Convert Path object to string for sys.path compatibility
        shared_path_str = str(shared_python_path)
        
        # Check if path is already in sys.path to avoid duplicates
        if shared_path_str not in sys.path:
            # Insert at beginning to prioritize our modules over system modules
            sys.path.insert(0, shared_path_str)
            print(f"Added to PYTHONPATH: {shared_path_str}")


def generate_env_file() -> None:
    """
    Generate .env file with cross-platform absolute paths for VS Code integration.
      Creates a .env file that VS Code's Python extension reads to configure
    the Python environment. Cross-platform features:
    - Uses absolute paths (no relative path issues)
    - Explicit UTF-8 encoding (consistent across platforms)
    - pathlib handles path separators automatically (\\ on Windows, / on Unix)
    - Works with VS Code's python.envFile setting
    """
    project_root = get_project_root()
    shared_python_path = project_root / 'shared' / 'python'
    
    # Create .env file content with absolute paths
    # These paths will be automatically correct for the current platform
    env_content = f"""# Auto-generated PYTHONPATH for VS Code - Run 'python setup/setup_python_path.py' to regenerate
PROJECT_ROOT={project_root}
PYTHONPATH={shared_python_path}
"""
    
    env_file_path = project_root / '.env'
    
    # Use explicit UTF-8 encoding for cross-platform text file compatibility
    # This ensures the file reads correctly on all operating systems
    with open(env_file_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print()
    print(f"Generated .env file : {env_file_path}")
    print(f"PROJECT_ROOT        : {project_root}")
    print(f"PYTHONPATH          : {shared_python_path}\n")


# Script entry point - handles command-line arguments
if __name__ == "__main__":
    # Check for --generate-env flag to create .env file for VS Code
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-env":
        generate_env_file()
    else:
        # Default behavior: modify current session's PYTHONPATH
        setup_python_path()
