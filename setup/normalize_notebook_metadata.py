#!/usr/bin/env python3

"""
Git clean filter that normalizes volatile Jupyter notebook metadata.

When configured as a git clean filter, this script reads notebook JSON from
stdin and writes it to stdout with `kernelspec.display_name` and
`language_info.version` set to fixed canonical values. This prevents
environment-specific Python version strings from appearing as git changes.

The local file keeps its real values (so VS Code / Jupyter work normally),
but git only ever sees the normalized output.

Usage as a git clean filter (configured automatically by local_setup.py):
    git config filter.notebook-metadata.clean "python setup/normalize_notebook_metadata.py"

Usage standalone (normalizes a file in-place):
    python setup/normalize_notebook_metadata.py <file.ipynb> [<file2.ipynb> ...]
"""

import json
import sys
from pathlib import Path

CANONICAL_DISPLAY_NAME = 'Python (.venv)'
CANONICAL_VERSION = '3.12.0'


def normalize_notebook_metadata(notebook: dict) -> dict:
    """Normalize volatile metadata fields in a parsed notebook dict.

    Replaces kernelspec.display_name and language_info.version with
    canonical values to avoid environment-specific git diffs.
    """
    metadata = notebook.get('metadata', {})

    kernelspec = metadata.get('kernelspec')
    if isinstance(kernelspec, dict) and 'display_name' in kernelspec:
        kernelspec['display_name'] = CANONICAL_DISPLAY_NAME

    language_info = metadata.get('language_info')
    if isinstance(language_info, dict) and 'version' in language_info:
        language_info['version'] = CANONICAL_VERSION

    return notebook


def normalize_stream(input_stream, output_stream) -> None:
    """Read a notebook from input_stream, normalize it, write to output_stream."""
    notebook = json.load(input_stream)
    normalize_notebook_metadata(notebook)
    json.dump(notebook, output_stream, indent=1, ensure_ascii=False)
    output_stream.write('\n')


def normalize_file(path: Path) -> bool:
    """Normalize a notebook file in-place. Returns True on success."""
    try:
        text = path.read_text(encoding='utf-8')
        notebook = json.loads(text)
        normalize_notebook_metadata(notebook)
        normalized = json.dumps(notebook, indent=1, ensure_ascii=False) + '\n'
        path.write_text(normalized, encoding='utf-8', newline='\n')

        return True
    except (json.JSONDecodeError, OSError) as exc:
        print(f"⚠️  Skipping {path}: {exc}", file=sys.stderr)

        return False


def main() -> None:
    """Entry point: filter stdin->stdout or normalize files given as arguments."""
    if len(sys.argv) > 1:
        # In-place mode: normalize listed files
        success = True
        for arg in sys.argv[1:]:
            path = Path(arg)
            if not path.exists():
                print(f"⚠️  File not found: {path}", file=sys.stderr)
                success = False
                continue
            if normalize_file(path):
                print(f"✅ Normalized {path}")
            else:
                success = False

        if not success:
            sys.exit(1)
    else:
        # Filter mode: stdin -> stdout (for git clean filter)
        normalize_stream(sys.stdin, sys.stdout)


if __name__ == '__main__':
    main()
