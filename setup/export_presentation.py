#!/usr/bin/env python3
"""Export the APIM Samples presentation as a self-contained HTML file with inlined images."""

import base64
import re
import sys
from pathlib import Path

# Ensure UTF-8 encoding for console output on Windows
if sys.platform == 'win32':  # pragma: no cover
    sys.stdout.reconfigure(encoding='utf-8')


def get_repo_root() -> Path:
    """Get the repository root path."""
    return Path(__file__).parent.parent


def inline_images(html_content: str, base_dir: Path) -> str:
    """
    Replace image src attributes with base64-encoded data URLs.

    Args:
        html_content: The HTML file content
        base_dir: The base directory for resolving relative paths

    Returns:
        HTML with inlined images
    """
    # Pattern to match img src and other image references
    # Matches: src="path/to/file.ext" or href="path/file.ext" for image files
    # Captures the attribute prefix and the full relative path including directories
    pattern = r'((?:src|href)=")([^"]*?\.(?:png|jpg|jpeg|gif|svg|webp))"'

    def replace_with_data_url(match):
        prefix = match.group(1)  # src=" or href="
        relative_path = match.group(2)  # Full path like "diagrams/filename.svg"

        # Try to find the file relative to base_dir
        image_path = base_dir / relative_path
        if not image_path.exists():
            # Walk upward so presentation assets can be resolved from nested folders.
            search_dirs: list[Path] = list(base_dir.parents) + [Path.cwd()]
            for search_dir in search_dirs:
                alt_path = search_dir / relative_path
                if alt_path.exists():
                    image_path = alt_path
                    break

        if not image_path.exists():
            print(f'  ⚠️  Warning: Image not found: {relative_path}')
            return match.group(0)  # Return unchanged

        # Determine MIME type
        suffix = image_path.suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp',
        }
        mime_type = mime_types.get(suffix, 'application/octet-stream')

        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('ascii')

        data_url = f'{prefix}data:{mime_type};base64,{image_data}"'

        # Print status message with relative path if possible
        try:
            rel_path = image_path.relative_to(get_repo_root())
            print(f'  ✓ Inlined: {relative_path} ({rel_path})')
        except ValueError:
            # Handle case where image_path is not under repo root (e.g., during tests)
            print(f'  ✓ Inlined: {relative_path}')

        return data_url

    return re.sub(pattern, replace_with_data_url, html_content, flags=re.IGNORECASE)


def strip_live_reload(html_content: str) -> str:
    """Remove the authoring-only live reload block from exported HTML."""
    pattern = re.compile(
        r'\n\s*// ── Live reload \(polls server for changes\) ──\n'
        r'\s*\(function \(\) \{.*?\}\)\(\);\n',
        flags=re.DOTALL,
    )

    return pattern.sub('\n', html_content, count=1)


def export_presentation():
    """Export the presentation as a self-contained HTML file."""
    repo_root = get_repo_root()
    presentation_dir = repo_root / 'assets'
    build_dir = repo_root / 'build'
    html_file = presentation_dir / 'APIM-Samples-Slide-Deck.html'
    output_file = build_dir / 'APIM-Samples-Slide-Deck.html'

    # Validate source file exists
    if not html_file.exists():
        print(f'\n❌ Error: Presentation file not found: {html_file}\n')
        sys.exit(1)

    # Create build directory
    build_dir.mkdir(exist_ok=True)
    print(f'\n📦 Exporting presentation to: {output_file.relative_to(repo_root)}\n')

    # Read HTML
    print('Reading presentation file...')
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Inline images
    print('\nInlining images...')
    html_with_inlined = inline_images(html_content, presentation_dir)

    # Standalone exports should not keep development-time live reload behavior.
    html_with_inlined = strip_live_reload(html_with_inlined)

    # Write output
    print('\nWriting output file...')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_with_inlined)

    # Print summary
    file_size_mb = output_file.stat().st_size / (1024 * 1024)
    print('\n✅ Export complete!')
    print(f'   Output: {output_file.relative_to(repo_root)}')
    print(f'   Size: {file_size_mb:.2f} MB')
    print('\n   📌 This is a self-contained file with all images inlined.')
    print('   📌 Ready to share or present offline.\n')


if __name__ == '__main__':  # pragma: no cover
    export_presentation()
