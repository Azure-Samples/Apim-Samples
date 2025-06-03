# PlantUML Diagrams

This directory contains PlantUML diagrams for the Azure API Management architecture.
Azure Symbols are on [GitHub](https://github.com/plantuml-stdlib/Azure-PlantUML/blob/master/AzureSymbols.md)

## Using PlantUML in VS Code

1. **Prerequisites**:
   - Java is installed (e.g. OpenJDK 22)
   - PlantUML VS Code extension is installed
   - Graphviz (optional, for more complex diagrams)
   - Configure PlantUML settings in `.vscode\settings.json`. Ensure that you set the `plantuml.java` path appropriately for your Java executable:

   ```json
   "plantuml.render": "Local",
   "plantuml.exportFormat": "svg",
   "plantuml.java": "C:\\Program Files\\OpenJDK\\jdk-22.0.2\\bin\\java.exe",
   "plantuml.diagramsRoot": "assets/diagrams/src",
   "plantuml.exportOutDir": "assets/diagrams/out"
   ```

2. **Viewing Diagrams**:
   - Open any `.puml` file in this directory
   - Right-click in the editor and select "PlantUML: Preview Current Diagram"
   - Alternatively, use the Alt+D keyboard shortcut

3. **Exporting Diagrams**:
   - Right-click in the editor and select "PlantUML: Export Current Diagram"
   - Select your desired output format (PNG, SVG, PDF, etc.)

## Troubleshooting

If you encounter issues with PlantUML:

1. **Java Path Issues**:
   - Ensure Java is on your system PATH
   - If VS Code terminal can't find Java, try restarting VS Code
   - You may need to configure the specific Java path in VS Code settings

2. **PlantUML Extension Configuration**:
   - Open VS Code settings (Ctrl+,)
   - Search for "plantuml"
   - Set "plantuml.java" to the path of your Java executable if needed
   - You can also set "plantuml.jarPath" to a specific PlantUML jar file

3. **Alternative Rendering**:
   - If local rendering fails, try using the PlantUML server:
   - Change "plantuml.render" setting to "PlantUMLServer"
