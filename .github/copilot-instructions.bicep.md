---
applyTo: "**/*.bicep"
---

# Copilot Instructions (Bicep)

## Goals

- Prefer modern Bicep syntax and patterns.
- Keep templates readable and easy to extend.
- Keep deployments cross-platform (Windows, Linux, macOS).

## Conventions

- Use `@description` for all parameters and variables.
- Prefer consistent naming:
  - Enums: `SNAKE_CASE` + uppercase.
  - Resources/variables: `camelCase`.
- Use the repo's standard top parameters when authoring standalone Bicep files:

```bicep
@description('Location to be used for resources. Defaults to the resource group location')
param location string = resourceGroup().location

@description('The unique suffix to append. Defaults to a unique string based on subscription and resource group IDs.')
param resourceSuffix string = uniqueString(subscription().id, resourceGroup().id)
```

## Structure

- Prefer visible section headers:

```bicep
// ------------------------------
//    PARAMETERS
// ------------------------------
```

- Keep two blank lines before a section header and one blank line after.
- Suggested order (when applicable): Parameters, Constants, Variables, Resources, Outputs.

## Docs

- Add a Microsoft Learn template reference comment above each resource, e.g.:

```bicep
// https://learn.microsoft.com/azure/templates/microsoft.network/virtualnetworks
resource vnet 'Microsoft.Network/virtualNetworks@<apiVersion>' = {
  ...
}
```
