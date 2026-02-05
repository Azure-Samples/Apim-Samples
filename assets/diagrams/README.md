# Mermaid Diagrams

This directory contains Mermaid diagrams for the Azure API Management architecture.

## About Azure Icons in Mermaid

**Important**: Unlike PlantUML, Mermaid does not have native Azure-specific stencils or icons. The diagrams in this repository use:

1. **Font Awesome icons** (e.g., `fa:fa-cloud`, `fa:fa-database`) to provide visual context
2. **Color coding** to distinguish component types:
   - Azure blue (#0078D4) for Azure services
   - Light blue (#ADD8E6) for applications
   - Light green (#90EE90) for APIs
3. **Clear labels** with Azure service names

### Why Not Official Azure Icons?

- Microsoft provides [official Azure icons](https://learn.microsoft.com/en-us/azure/architecture/icons/) as SVG/PNG files
- These are designed for tools like Visio, PowerPoint, or Draw.io
- Mermaid does not support importing custom icon sets directly
- For high-fidelity branded diagrams, use tools like Draw.io or Visio with official Azure icons

### Font Awesome Icon Support

The diagrams use Font Awesome icons (v5+) with the `fa:fa-icon-name` syntax. Icon support depends on your rendering environment:

- ✅ **Mermaid Live Editor**: Full support
- ✅ **VS Code with Mermaid extension**: Supported (requires Font Awesome stylesheet)
- ✅ **GitHub Markdown**: Supported in most renderers
- ⚠️ **Azure DevOps Wiki**: Limited support (may not render icons)
- ⚠️ **Some static site generators**: May require Font Awesome CDN configuration

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

2. **Icons Not Showing**:
   - Font Awesome icons may not render in all environments
   - The diagram structure and labels will still be clear without icons
   - For web rendering, ensure Font Awesome CSS is loaded:
     ```html
     <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
     ```

3. **Syntax Errors**:
   - Validate your Mermaid syntax using [Mermaid Live Editor](https://mermaid.live)
   - Check for proper indentation and formatting
   - Ensure all node IDs are unique

4. **Export Issues**:
   - For CLI exports, ensure `@mermaid-js/mermaid-cli` is installed globally
   - Check that Puppeteer dependencies are installed (required for mermaid-cli)
