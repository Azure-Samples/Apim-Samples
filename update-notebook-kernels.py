#!/usr/bin/env python3
"""
Update notebook kernel metadata to use APIM Samples kernel.

This script updates all Jupyter notebooks in the workspace to use
the correct kernelspec metadata so they default to our venv kernel.
"""

import json
import os
import sys
from pathlib import Path

def update_notebook_kernel(notebook_path):
    """Update a single notebook's kernel metadata."""
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        # Update kernelspec metadata
        if 'metadata' not in notebook:
            notebook['metadata'] = {}
        
        notebook['metadata']['kernelspec'] = {
            "display_name": "APIM Samples Python 3.12",
            "language": "python", 
            "name": "apim-samples"
        }
        
        notebook['metadata']['language_info'] = {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.12.10"
        }
        
        # Write back the updated notebook
        with open(notebook_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=1, ensure_ascii=False)
        
        print(f"✅ Updated: {notebook_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating {notebook_path}: {e}")
        return False

def main():
    """Update all notebooks in the workspace."""
    workspace_root = Path(__file__).parent
    updated_count = 0
    error_count = 0
    
    print("🔧 Updating notebook kernel metadata...")
    print(f"Workspace: {workspace_root}")
    print()
    
    # Find all .ipynb files
    notebook_files = list(workspace_root.rglob("*.ipynb"))
    
    if not notebook_files:
        print("No notebook files found.")
        return 0
    
    print(f"Found {len(notebook_files)} notebook files:")
    
    for notebook_path in notebook_files:
        rel_path = notebook_path.relative_to(workspace_root)
        print(f"Processing: {rel_path}")
        
        if update_notebook_kernel(notebook_path):
            updated_count += 1
        else:
            error_count += 1
    
    print()
    print(f"📊 Summary:")
    print(f"   Updated: {updated_count}")
    print(f"   Errors:  {error_count}")
    print(f"   Total:   {len(notebook_files)}")
    
    if error_count == 0:
        print("🎉 All notebooks updated successfully!")
        return 0
    else:
        print("⚠️  Some notebooks had errors.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
