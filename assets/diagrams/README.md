# Architecture Diagrams

This directory contains Draw.io architecture diagrams (`.drawio`) and their SVG exports (`.svg`) for the Azure API Management infrastructures.

## Using Draw.io in VS Code

1. **Prerequisites**:
   - Install the [Draw.io Integration][vscode-drawio] VS Code extension

2. **Viewing and Editing Diagrams**:
   - Open any `.drawio` file in this directory
   - The Draw.io editor opens directly inside VS Code
   - **Set the page background to white** to ensure readability in dark mode: Edit > Page Setup > Background > `#FFFFFF`

3. **Exporting Diagrams**:
   - Right-click the `.drawio` file in the Explorer and select "Export"
   - Select SVG as the output format
   - Save the `.svg` file alongside the `.drawio` source in this directory

## Conventions

- Each infrastructure has a corresponding `.drawio` and `.svg` file in this directory.
- Infrastructure README files reference the `.svg` exports from this folder.
- Always export SVGs with a **white background**. Transparent backgrounds are difficult to read in dark mode.
- Keep diagrams simple and focused on major architectural components.

## Tooling

The Draw.io diagrams in this repository were created with the [Azure Draw.io MCP Server][drawio-mcp-server]. It is an MCP server for Draw.io that provides Azure architecture icons and streamlined diagram generation.

[drawio-mcp-server]: https://github.com/simonkurtz-MSFT/drawio-mcp-server
[vscode-drawio]: https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio
