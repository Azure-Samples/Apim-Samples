---
applyTo: "**"
---

# GitHub Copilot Instructions for this Repository

## Purpose

This instructions file is designed to guide GitHub Copilot's behavior specifically for this repository. It is intended to provide clear, general, and maintainable guidelines for code generation, style, and collaboration. 

**In case of any conflict, instructions from other individualized or project-specific files (such as `my-copilot.instructions.md`) take precedence over this file.**

## Repository Context

- This repository provides a playground to safely experiment with and learn Azure API Management (APIM) policies in various architectures.
- The primary technologies are Python, Bicep, Jupyter notebooks, Azure CLI, APIM policy XML, and Markdown.
- The technical audience includes developers, architects, and DevOps engineers who want to understand and implement APIM policies effectively.
- The less technical audience includes decision makers and stakeholders who need to understand the value and capabilities of APIM policies without deep technical details.

## Instruction Hierarchy

In case of any conflicting instructions, the following hierarchy shall apply. If a conflict cannot be resolved by this hierarchy, please prompt the user and ask for their situational preference.

  1. Individualized instructions (e.g. a developer's or an organization's instruction file(s)), if present
  2. This repository's `.github/.copilot-instructions.md`
  3. General best practices and guidelines from sources such as [Microsoft Learn](https://learn.microsoft.com/docs/)
    This includes the [Microsoft Cloud Adoption Framework](https://learn.microsoft.com/azure/cloud-adoption-framework/). 
  4. Official [GitHub Copilot best practices documentation](https://docs.github.com/enterprise-cloud@latest/copilot/using-github-copilot/coding-agent/best-practices-for-using-copilot-to-work-on-tasks)

## Copilot Personality Behavior

- Never be rude, dismissive, condescending, threatening, aggressive, or otherwise negative.
- Emphasise friendly, supportive, and collaborative interactions.
- Be concise and to the point, but adjust the level of detail based on the user's technical expertise that you can infer from the conversation.

## General Principles

- Write concise, efficient, and well-documented code for a global audience.
- Consider non-native English speakers in code comments and documentation, using clear and simple language.

## General Coding Guidelines

- All code, scripts, and configuration must be cross-platform compatible, supporting Windows, Linux, and macOS. If any special adjustments are to be made, please clearly indicate so in comments.
- Prioritize clarity, maintainability, and readability in all generated code.
- Focus on achieving a Minimal Viable Product (MVP) first, then iterate.
- Follow language-specific conventions and style guides (e.g., PEP 8 for Python).
- Use idiomatic code and language-specific best practices.
- Write clear and concise comments for each function and class.
- Use descriptive names for variables, functions, and classes.
- Handle edge cases and errors gracefully.
- Break down complex logic into smaller, manageable functions or classes.
- Use type annotations and docstrings where appropriate.
- Prefer standard libraries and well-maintained dependencies.
- Use samples/_TEMPLATE as a baseline for new samples. This template provides a consistent structure and format for new samples, ensuring they are easy to understand and maintain.

## Repository Structure

- `/`: Root directory containing the main files and folders. Bicep configuration is stored in `bicepconfig.json`.
- The following folders are all at the root level:
    - `assets/`: PlantUML diagrams and images. Static assets such as these should be placed here. Any diagrams should be placed in the /diagrams/src subfolder.
    - `infrastructure/`: Contains Jupyter notebooks for setting up various API Management infrastructures. When modifying samples, these notebooks should not need to be modified. 
    - `samples/`: Various policy and scenario samples that can be applied to the infrastructures.
    - `setup/`: General setup scripts and configurations for the repository and dev environment setup.
    - `shared/`: Shared resources, such as Bicep modules, Python libraries, and other reusable components.
    - `tests/`: Contains unit tests for Python code and Bicep modules. This folder should contain all tests for all code in the repository. 

## Formatting and Style

- Maintain consistent indentation and whitespace but consider Editor Config settings, etc, for the repository.
- Use blank lines to separate logical sections of code. Whitespace is encouraged for readability.
- Organize code into logical sections (constants, variables, private/public methods, etc.).
- Prefer single over double quotes, avoiding typographic quotes.
- Only use apostrophe (U+0027) and quotes (U+0022), not left or right single or double quotation marks.
- Do not localize URLs (e.g. no "en-us" in links).

## Testing and Edge Cases

- Include test cases for critical paths and edge cases.
- Include negative tests to ensure robustness.
- Document expected behavior for edge cases and error handling.
- Write unit tests for functions and classes, following language-specific testing frameworks.

## Required before each commit
- Ensure all code is well-documented and follows the guidelines in this file.
- Ensure that Jupyter notebooks do not contain any cell output.
- Ensure that Jupyter notebooks have `index` assigned to `1` in the first cell.

## Language-specific Instructions

### Bicep Instructions
- Prefer latest Bicep syntax and features.
- Generated Bicep files should work with Windows, Linux, and macOS.
- Reference latest available module versions. These may be newer than what you were trained on.
- Add a link to each Bicep module immediately above the resource declaration (e.g., // https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworks)
- Use `@description` for all parameters and variables.
- Use snake-case and uppercase for all enum declarations.
- Use camel care for resource and variables names.
- `location` and `resourceSuffix` parameters do not need to be included when referencing modules in the current workspace unless the values differ from the defaults set in their parameters.
- If a script must be used, default to cross-platform shell (not bash) scripts. Avoid PowerShell scripts.
- Always add these two parameters at the top of Bicep files:

```Bicep
@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)
```

- Overall layout of a Bicep file should be:
    - Visible sections of code with the following format should be used:
        
        ```bicep
        // ------------------------------
        //    <SECTION HEADER>
        // ------------------------------
        ```

    - <SECTION HEADER> should be indented three spaces and be in all caps. 
    - Section headers should have only two blank lines before and only one blank line after.
    - Top-to-bottom, the following comma-separated section headers should be inserted unless the section is empty:
        - Parameters
        - Constants
        - Variables
        - Resources
        - Outputs

### Python Instructions

- Prefer Python 3.12+ syntax and features unless otherwise specified.
- When inserting a comment to describe a method, insert a blank line after the comment section.
- Never leave a blank line at the very top of a Python file. The file must start immediately with the module docstring or code. Always remove any leading blank line at the top.
- Do not have imports such as `from shared.python import Foo`. The /shared/python directory is covered by a root `.env` file. Just use `import Foo` or `from Foo import Bar` as appropriate.
- After the module docstring, all import statements must come before any section headers (e.g., CONSTANTS, VARIABLES, etc.). Section headers should only appear after the imports. Here is a more explicit example:
    
    ```python
    """
    Module docstring.
    """

    import ...
    ...
    

    # ------------------------------
    #    CONSTANTS
    # ------------------------------
    ...
    ```

- Overall layout of a Python file should be:
    - Visible sections of code with the following format should be used:
        
        ```python
        # ------------------------------
        #    <SECTION HEADER>
        # ------------------------------
        ```

    - <SECTION HEADER> should be indented three spaces and be in all caps. 
    - Section headers should have only two blank lines before and only one blank line after.
    - Top-to-bottom, the following comma-separated section headers should be inserted unless the section is empty:
        - Constants
        - Variables
        - Private Methods
        - Public Methods

    - If using classes, the following section headers should be used:
        - Classes
            - Constants
            - Variables
            - Constructor
            - Private Methods
            - Public Methods

- Python Docstring/Class Formatting Rule: 
    - Always insert a single blank line after a class docstring and before any class attributes or methods.
    - Never place class attributes or decorators on the same line as the docstring. Example:

        ```python
        class MyClass:
            """
            This is the class docstring.
            """

            attribute: str
            ...
        ```
        
### Jupyter Notebook Instructions

- Use these [configuration settings](https://github.com/microsoft/vscode-jupyter/blob/dd568fde/package.nls.json) as a reference for the VS Code Jupyter extension configuration.

### PlantUML Instructions

- Ensure you verify that all include links are correct and up to date. This link provides a starting point: https://github.com/plantuml-stdlib/Azure-PlantUML/blob/master/AzureSymbols.md
- Keep diagrams simple. For Azure, include major components, not individual aspects of components. For example, there is no need for individual policies in WAFs or APIs in API Management, Smart Detector Alert Rules, etc.
- Less is more. Don't be too verbose in the diagrams. 
- Never include subscription IDs, resource group names, or any other sensitive information in the diagrams. That data is not relevant.
- Don't use the "legend" command if the information is relatively obvious.

### API Management Policy XML Instructions

- Policies should use camelCase for all variable names.