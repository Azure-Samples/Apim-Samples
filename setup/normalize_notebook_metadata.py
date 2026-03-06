#!/usr/bin/env python3

"""
Git clean filter that normalizes volatile Jupyter notebook metadata and
scrubs all cell outputs.

When configured as a git clean filter, this script reads notebook JSON from
stdin and writes it to stdout with:

- `kernelspec.display_name` and `language_info.version` set to fixed
  canonical values (prevents environment-specific Python version strings
  from appearing as git changes).
- Every code cell's `outputs` cleared to `[]` and `execution_count` reset
  to `null` (prevents run-time output, which can contain subscription IDs,
  resource names, tokens, etc., from ever being committed).

The local file keeps its real values and outputs (so VS Code / Jupyter work
normally and you can still see what you just ran), but git only ever sees
the normalized, scrubbed representation.

Usage as a git clean filter (configured automatically by local_setup.py):
    git config filter.notebook-metadata.clean "python setup/normalize_notebook_metadata.py"

Usage standalone (normalizes only uncommitted notebooks — the default):
    python setup/normalize_notebook_metadata.py
    python setup/normalize_notebook_metadata.py --uncommitted

Usage standalone (normalizes specific files in-place):
    python setup/normalize_notebook_metadata.py <file.ipynb> [<file2.ipynb> ...]
"""

import json
import subprocess
import sys
from pathlib import Path

CANONICAL_DISPLAY_NAME = 'Python (.venv)'
CANONICAL_VERSION = '3.12.0'


def scrub_cell_outputs(notebook: dict) -> dict:
    """Clear outputs and execution counts from every code cell.

    Code cells have their ``outputs`` replaced with an empty list and their
    ``execution_count`` reset to ``None``.  Non-code cells (markdown, raw)
    are left untouched since they carry no execution state.  Keys that are
    absent stay absent; we only overwrite what is already there.
    """
    cells = notebook.get('cells')
    if not isinstance(cells, list):
        return notebook

    for cell in cells:
        if not isinstance(cell, dict) or cell.get('cell_type') != 'code':
            continue

        if 'outputs' in cell:
            cell['outputs'] = []

        if 'execution_count' in cell:
            cell['execution_count'] = None

    return notebook


def normalize_notebook_metadata(notebook: dict) -> dict:
    """Normalize volatile metadata fields and scrub outputs in a notebook dict.

    Replaces ``kernelspec.display_name`` and ``language_info.version`` with
    canonical values to avoid environment-specific git diffs, then strips
    all code-cell outputs and execution counts so run-time output never
    lands in the index.
    """
    metadata = notebook.get('metadata', {})

    kernelspec = metadata.get('kernelspec')
    if isinstance(kernelspec, dict) and 'display_name' in kernelspec:
        kernelspec['display_name'] = CANONICAL_DISPLAY_NAME

    language_info = metadata.get('language_info')
    if isinstance(language_info, dict) and 'version' in language_info:
        language_info['version'] = CANONICAL_VERSION

    scrub_cell_outputs(notebook)

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
        print(f'⚠️  Skipping {path}: {exc}', file=sys.stderr)

        return False


def get_uncommitted_notebooks() -> list[Path]:
    """Return notebook paths that have uncommitted changes (staged or unstaged).

    Runs ``git diff`` to find modified/added ``.ipynb`` files in both the
    working tree and the index relative to HEAD.
    """
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=ACMR', 'HEAD', '--', '*.ipynb'],
            capture_output=True,
            text=True,
            check=True,
        )
        staged = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=ACMR', '--staged', '--', '*.ipynb'],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f'⚠️  Could not query git for uncommitted files: {exc}', file=sys.stderr)

        return []

    paths: set[str] = set()
    for line in (result.stdout + staged.stdout).splitlines():
        stripped = line.strip()
        if stripped:
            paths.add(stripped)

    return [Path(p) for p in sorted(paths)]


def main() -> None:
    """Entry point: normalize uncommitted notebooks, specific files, or filter stdin.

    When invoked with no arguments from an interactive terminal, the script
    defaults to ``--uncommitted`` behaviour and normalizes only ``.ipynb``
    files with pending changes.  When stdin is piped (e.g. by the git clean
    filter), it reads a notebook from stdin and writes the normalised version
    to stdout.

    Flags:
        --uncommitted   Discover and normalize only ``.ipynb`` files with
                        pending (uncommitted) changes.  This is the default
                        when no file arguments are given interactively.
    """
    args = sys.argv[1:]
    uncommitted = '--uncommitted' in args

    if uncommitted:
        args.remove('--uncommitted')

    # Default to --uncommitted when no files are given and stdin is a TTY
    # (interactive terminal).  When stdin is piped, fall through to filter mode.
    if not args and not uncommitted and sys.stdin.isatty():
        uncommitted = True

    if uncommitted:
        if args:
            print('⚠️  --uncommitted does not accept extra file arguments.', file=sys.stderr)
            sys.exit(1)

        files = get_uncommitted_notebooks()
        if not files:
            print('ℹ️  No uncommitted notebook changes found.')

            return

        # Normalize the discovered files
        sys.argv = [sys.argv[0]] + [str(f) for f in files]
        args = sys.argv[1:]

    if args:
        # In-place mode: normalize listed files
        success = True
        for arg in args:
            path = Path(arg)
            if not path.exists():
                print(f'⚠️  File not found: {path}', file=sys.stderr)
                success = False
                continue
            if normalize_file(path):
                print(f'✅ Normalized {path}')
            else:
                success = False

        if not success:
            sys.exit(1)
    else:
        # Filter mode: stdin -> stdout (for git clean filter)
        normalize_stream(sys.stdin, sys.stdout)


if __name__ == '__main__':
    main()
