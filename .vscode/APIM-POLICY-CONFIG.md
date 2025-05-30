# VS Code Configuration for APIM Policy Development

This document explains the VS Code configuration optimized for working with Azure API Management (APIM) policy files.

## Overview

APIM policies are XML files that often contain C# expressions, making them challenging to validate with standard XML tools. This configuration provides the best balance of helpful features while avoiding false validation errors.

## Extensions Required

The following extensions are required for optimal APIM policy development:

1. **Azure API Management** (`ms-azuretools.vscode-apimanagement`) - Provides APIM-specific features
2. **XML** (`redhat.vscode-xml`) - XML language support with formatting and basic validation
3. **Auto Close Tag** (`formulahendry.auto-close-tag`) - Automatically closes XML tags
4. **Auto Rename Tag** (`formulahendry.auto-rename-tag`) - Renames paired XML tags

## Key Configuration Settings

### XML Validation
```json
"xml.validation.enabled": true,
"xml.validation.namespaces.enabled": "never",
"xml.validation.schema.enabled": "never"
```
- Enables basic XML syntax validation but disables strict schema and namespace validation
- Prevents false errors on APIM-specific elements and C# expressions

### File Associations
```json
"files.associations": {
    "*.xml": "xml",
    "**/apim-policies/*.xml": "xml",
    "**/samples/**/*.xml": "xml",
    "pf-*.xml": "xml",
    "hr_*.xml": "xml"
}
```
- Ensures all APIM policy files are treated as XML
- Covers policy fragments (pf-*.xml) and sample files

### Validation Filters
```json
"xml.validation.filters": [
    {
        "pattern": "**/apim-policies/*.xml",
        "noGrammar": "ignore"
    },
    {
        "pattern": "**/samples/**/*.xml", 
        "noGrammar": "ignore"
    }
]
```
- Suppresses "no grammar" warnings for APIM policy files
- Allows VS Code to provide formatting and basic syntax checking without schema validation errors

### APIM-Specific Settings
```json
"azureApiManagement.policies.validateSyntax": true,
"azureApiManagement.policies.showCodeLens": true
```
- Enables APIM extension's built-in policy syntax validation
- Shows code lens information for policy elements

## Features Enabled

1. **XML Formatting**: Automatic formatting with proper indentation
2. **Tag Auto-completion**: Auto-closing and auto-renaming of XML tags
3. **Syntax Highlighting**: Full XML syntax highlighting
4. **APIM Policy Validation**: Basic validation through the APIM extension
5. **Quick Suggestions**: Intelligent suggestions for XML content
6. **Bracket Matching**: Automatic closing of brackets and quotes

## Working with C# Expressions

APIM policies often contain C# expressions within XML attributes and content. The configuration:

- Allows C# code within XML without validation errors
- Preserves formatting of C# expressions
- Provides basic bracket matching for C# code

Example C# expression in APIM policy:
```xml
<set-variable name="authz_roles" value="{{HRAdministratorRoleId}},{{HRAssociateRoleId}}" />
<when condition="@(((Jwt)context.Variables[&quot;jwt&quot;]).Claims[&quot;roles&quot;].Contains(context.Variables[&quot;authz_roles&quot;]))">
```

## Common APIM Policy Elements

The configuration recognizes and provides support for common APIM policy elements:

- `<policies>`, `<inbound>`, `<outbound>`, `<backend>`, `<on-error>`
- `<set-variable>`, `<set-header>`, `<set-body>`
- `<validate-jwt>`, `<cors>`, `<rate-limit>`
- `<choose>`, `<when>`, `<otherwise>`
- `<return-response>`, `<forward-request>`
- `<include-fragment>` for policy fragments

## Troubleshooting

### Schema Validation Errors
If you see schema validation errors:
1. Check that `xml.validation.schema.enabled` is set to `"never"`
2. Verify the validation filters are correctly configured
3. Ensure the APIM extension is installed and enabled

### Missing Intellisense
If you're not getting XML completion:
1. Verify the file is recognized as XML (check the language mode in the status bar)
2. Ensure `xml.completion.autoCloseTags` is enabled
3. Check that the file associations are correctly configured

### C# Expression Errors
If C# expressions in policies show errors:
- This is normal - VS Code cannot fully validate C# within XML context
- The APIM extension provides the actual validation
- Use the APIM test console for runtime validation

## Best Practices

1. **Use Policy Fragments**: Create reusable policy fragments for common patterns
2. **Test in APIM**: Always test policies in the actual APIM instance
3. **Format Regularly**: Use VS Code's format document command (`Shift+Alt+F`)
4. **Use Named Values**: Reference configuration through APIM named values
5. **Comment Policies**: Use XML comments to document complex policy logic

## Files Created

- `.vscode/settings.json` - Main VS Code configuration
- `.vscode/extensions.json` - Recommended extensions
- `.vscode/apim-policy.xsd` - Basic XSD schema for APIM policies (reference only)
- `.vscode/xml-catalog.xml` - XML catalog for schema resolution (if needed)

This configuration provides an optimal development experience for APIM policies while avoiding the common validation errors that occur when using generic XML tools with APIM-specific content.
