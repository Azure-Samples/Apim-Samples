"""Small utility to strip trailing whitespace and ensure final newline for .py files under tests/python.
Run from the repo root: py -3 tools/fix_trailing_whitespace.py
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
pattern = root / 'tests' / 'python'
if not pattern.exists():
    print(f"Path not found: {pattern}")
    raise SystemExit(1)

fixed_files = []
for p in pattern.rglob('*.py'):
    text = p.read_text(encoding='utf-8')
    # Normalize line endings
    lines = text.splitlines()
    new_lines = [ln.rstrip() for ln in lines]
    new_text = "\n".join(new_lines) + "\n"
    if new_text != text:
        p.write_text(new_text, encoding='utf-8')
        fixed_files.append(str(p.relative_to(root)))

print(f"Fixed {len(fixed_files)} files")
for f in fixed_files:
    print(f" - {f}")
