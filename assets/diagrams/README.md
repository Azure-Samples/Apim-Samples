# Mermaid Diagrams

This directory contains Mermaid diagrams for the Azure API Management architecture.

## Using Mermaid in VS Code

1. **Prerequisites**:
   - Mermaid VS Code extension is installed (recommended: `bierner.markdown-mermaid`)
   - No additional software required - Mermaid renders natively in Markdown

2. **Viewing Diagrams**:
   - Open any `.md` file in the `src` directory
   - The Mermaid diagrams will render automatically in VS Code's Markdown preview
   - Use `Ctrl+Shift+V` (Windows/Linux) or `Cmd+Shift+V` (macOS) to open Markdown preview
   - Right-click in the editor and select "Markdown: Open Preview to the Side" for side-by-side view

3. **Exporting Diagrams**:
   - Use the Mermaid CLI for exporting: `npm install -g @mermaid-js/mermaid-cli`
   - Export to SVG: `mmdc -i diagram.md -o diagram.svg`
   - Export to PNG: `mmdc -i diagram.md -o diagram.png`
   - Alternatively, use online tools like [Mermaid Live Editor](https://mermaid.live) for quick exports

## Troubleshooting

If you encounter issues with Mermaid:

1. **Diagrams Not Rendering**:
   - Ensure the Mermaid extension is installed and enabled
   - Check that Markdown preview is active
   - Try reloading VS Code

2. **Syntax Errors**:
   - Validate your Mermaid syntax using [Mermaid Live Editor](https://mermaid.live)
   - Check for proper indentation and formatting
   - Ensure all node IDs are unique

3. **Export Issues**:
   - For CLI exports, ensure `@mermaid-js/mermaid-cli` is installed globally
   - Check that Puppeteer dependencies are installed (required for mermaid-cli)
