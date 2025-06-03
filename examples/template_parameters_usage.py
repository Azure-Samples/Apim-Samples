#!/usr/bin/env python3
"""
Example usage of templateParameters support in APIMTypes.

This example demonstrates how to create API operations with template parameters
that match URL template variables used in APIM operations.
"""

import sys
import os

# Add the shared python module to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'shared', 'python'))

from apimtypes import API, APIOperation, GET_APIOperation2, HTTP_VERB

def create_blob_access_api_example():
    """
    Example: Create an API with a blob access operation that uses template parameters.
    
    This matches the secure-blob-access sample where we need:
    - URL Template: /blobs/{blob-name}
    - Template Parameter: blob-name (required, string)
    """
    
    # Define template parameters for the blob name
    blob_template_parameters = [
        {
            "name": "blob-name",
            "description": "The name of the blob to access",
            "type": "string",
            "required": True
        }
    ]
    
    # Read the policy XML (in a real scenario, you'd read from the actual file)
    # For this example, we'll use a simple mock policy
    blob_policy_xml = """<policies>
    <inbound>
        <base />
        <set-backend-service base-url="https://yourstorageaccount.blob.core.windows.net/container" />
        <rewrite-uri template="/{{blob-name}}" />
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>"""
    
    # Create the GET operation with template parameters
    blob_get_operation = GET_APIOperation2(
        name="get-blob",
        displayName="Get Blob",
        urlTemplate="/blobs/{blob-name}",
        description="Retrieve a blob by name",
        policyXml=blob_policy_xml,
        templateParameters=blob_template_parameters
    )
      # Create the API with the operation (use explicit policy to avoid file path issues)
    simple_policy = """<policies>
    <inbound>
        <base />
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>"""
    
    blob_api = API(
        name="blob-access-api",
        displayName="Blob Access API", 
        path="/blob",
        description="API for secure blob access",
        policyXml=simple_policy,
        operations=[blob_get_operation]
    )
    
    return blob_api

def create_user_management_api_example():
    """
    Example: Create a user management API with multiple template parameters.
    """
    
    # Template parameters for user operations
    user_template_parameters = [
        {
            "name": "user-id",
            "description": "The unique identifier of the user",
            "type": "string", 
            "required": True
        },
        {
            "name": "department",
            "description": "The department code",
            "type": "string",
            "required": False
        }
    ]
      # Create a user operation using the base APIOperation class (with explicit policy)
    user_policy = """<policies>
    <inbound>
        <base />
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>"""
    
    get_user_operation = APIOperation(
        name="get-user-by-dept",
        displayName="Get User by Department",
        urlTemplate="/users/{user-id}/department/{department}",
        method=HTTP_VERB.GET,
        description="Get user information filtered by department",
        policyXml=user_policy,
        templateParameters=user_template_parameters
    )
    
    # Create the API (with explicit policy)
    user_api = API(
        name="user-management-api",
        displayName="User Management API",
        path="/users",
        description="API for user management operations",
        policyXml=user_policy,
        operations=[get_user_operation]
    )
    
    return user_api

def main():
    """
    Demonstrate the usage of templateParameters in API operations.
    """
    
    print("=== APIMTypes templateParameters Usage Examples ===\n")
    
    # Example 1: Blob access API
    print("1. Blob Access API Example:")
    blob_api = create_blob_access_api_example()
    blob_dict = blob_api.to_dict()
    
    print(f"   API Name: {blob_dict['name']}")
    print(f"   API Path: {blob_dict['path']}")
    
    if blob_dict['operations']:
        operation = blob_dict['operations'][0]
        print(f"   Operation: {operation['name']}")
        print(f"   URL Template: {operation['urlTemplate']}")
        print(f"   Template Parameters: {len(operation.get('templateParameters', []))}")
        
        for param in operation.get('templateParameters', []):
            print(f"     - {param['name']}: {param['description']} (required: {param.get('required', False)})")
    
    print()
    
    # Example 2: User management API  
    print("2. User Management API Example:")
    user_api = create_user_management_api_example()
    user_dict = user_api.to_dict()
    
    print(f"   API Name: {user_dict['name']}")
    print(f"   API Path: {user_dict['path']}")
    
    if user_dict['operations']:
        operation = user_dict['operations'][0]
        print(f"   Operation: {operation['name']}")
        print(f"   URL Template: {operation['urlTemplate']}")
        print(f"   Template Parameters: {len(operation.get('templateParameters', []))}")
        
        for param in operation.get('templateParameters', []):
            print(f"     - {param['name']}: {param['description']} (required: {param.get('required', False)})")
    
    print("\n=== Conversion to Bicep-compatible format ===")
    print("These API objects can now be serialized and passed to Bicep templates")
    print("that support the templateParameters property for APIM operations.")

if __name__ == "__main__":
    main()
