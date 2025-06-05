# Azure APIM templateParameters Support

The Python APIMTypes now support optional `templateParameters` for API operations. This resolves the issue where APIM operations with template parameters in their URL templates (like `/{blob-name}`) would fail with the error:

> "All template parameters used in the UriTemplate must be defined in the Operation"

## What was changed

1. **Bicep module** (`shared/bicep/modules/apim/v1/api.bicep`): Added support for optional `templateParameters` using the safe access operator:
   ```bicep
   templateParameters: op.?templateParameters ?? []
   ```

2. **Python APIMTypes** (`shared/python/apimtypes.py`): Added optional `templateParameters` field to:
   - `APIOperation` base class
   - `GET_APIOperation2` class (most commonly used for operations with parameters)

## Usage Example

### Before (would cause deployment error):
```python
blob_get = GET_APIOperation2('GET', 'GET', '/{blob-name}', 'Gets the blob access valet key', blob_get_policy_xml)
```

### After (with templateParameters):
```python
# Define template parameters for the {blob-name} parameter
blob_name_template_params = [
    {
        "name": "blob-name",
        "description": "The name of the blob to access",
        "type": "string",
        "required": True
    }
]

# Create operation with template parameters
blob_get = GET_APIOperation2(
    name='GET',
    displayName='GET', 
    urlTemplate='/{blob-name}', 
    description='Gets the blob access valet key',
    policyXml=blob_get_policy_xml,
    templateParameters=blob_name_template_params
)
```

## Template Parameter Format

Template parameters should be a list of dictionaries with the following properties:

```python
{
    "name": "parameter-name",           # Required: matches the parameter in URL template
    "description": "Parameter description",  # Optional: human-readable description  
    "type": "string",                   # Optional: parameter type (string, int, etc.)
    "required": True                    # Optional: whether parameter is required
}
```

## Common Use Cases

1. **Blob/File Access**: `/{file-name}`, `/{blob-name}`
2. **Resource IDs**: `/{user-id}`, `/{product-id}`
3. **Nested Resources**: `/{category}/{item-id}`

## Backward Compatibility

The `templateParameters` field is optional, so existing code will continue to work without changes. However, operations with template parameters in their URL templates should add the `templateParameters` field to avoid deployment errors.
