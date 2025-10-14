"""Add a module-level pylint disable for import-outside-toplevel (C0415)
for all .py files under tests/python that don't already include it.
Run from repo root: py -3 tools/disable_c0415_in_tests.py
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
tests_dir = root / 'tests' / 'python'
if not tests_dir.exists():
    print(f"tests/python not found: {tests_dir}")
    raise SystemExit(1)

pattern = '**/*.py'
modified = []
for p in sorted(tests_dir.rglob('*.py')):
    txt = p.read_text(encoding='utf-8')
    # If the disable is already present, skip
    if 'pylint: disable=import-outside-toplevel' in txt:
        continue
    # Find first non-shebang, non-encoding line to insert after any #! or encoding comments
    lines = txt.splitlines()
    insert_at = 0
    # skip shebang
    if lines and lines[0].startswith('#!'):
        insert_at = 1
    # skip encoding comment on first or second line
    if len(lines) > insert_at and ('coding' in lines[insert_at] or 'coding' in ''.join(lines[insert_at])):
        insert_at += 1
    # Build new content
    disable_line = '# pylint: disable=import-outside-toplevel'
    # Preserve leading blank lines if present
    new_lines = lines[:insert_at] + [disable_line] + lines[insert_at:]
    new_text = '\n'.join(new_lines) + ('\n' if txt.endswith('\n') else '')
    p.write_text(new_text, encoding='utf-8')
    modified.append(str(p.relative_to(root)))

print(f"Updated {len(modified)} files to disable C0415")
for m in modified:
    print(' -', m)
