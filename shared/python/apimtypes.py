"""
Types and constants for Azure API Management automation and deployment.
"""

from enum import StrEnum
from dataclasses import dataclass
from typing import List, Optional


# ------------------------------
#    CONSTANTS
# ------------------------------

# These paths are relative to the infrastructure and samples
SHARED_XML_POLICY_BASE_PATH         = '../../shared/apim-policies'
DEFAULT_XML_POLICY_PATH             = f'{SHARED_XML_POLICY_BASE_PATH}/default.xml'
HELLO_WORLD_XML_POLICY_PATH         = f'{SHARED_XML_POLICY_BASE_PATH}/hello-world.xml'
REQUEST_HEADERS_XML_POLICY_PATH     = f'{SHARED_XML_POLICY_BASE_PATH}/request-headers.xml'
ACA_BACKEND_1_XML_POLICY_PATH       = f'{SHARED_XML_POLICY_BASE_PATH}/aca-backend-1.xml'
ACA_BACKEND_2_XML_POLICY_PATH       = f'{SHARED_XML_POLICY_BASE_PATH}/aca-backend-2.xml'
ACA_BACKEND_POOL_XML_POLICY_PATH    = f'{SHARED_XML_POLICY_BASE_PATH}/aca-backend-pool.xml'

SUBSCRIPTION_KEY_PARAMETER_NAME = 'api_key'
SLEEP_TIME_BETWEEN_REQUESTS_MS  = 50

# Mock role IDs for testing purposes
HR_MEMBER_ROLE_ID          = "316790bc-fbd3-4a14-8867-d1388ffbc195"
HR_ASSOCIATE_ROLE_ID       = "d3c1b0f2-4a5e-4c8b-9f6d-7c8e1f2a3b4c"
HR_ADMINISTRATOR_ROLE_ID   = "a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6"


# ------------------------------
#    PRIVATE METHODS
# ------------------------------

# Placing this here privately as putting it into the utils module would constitute a circular import
def _read_policy_xml(policy_xml_filepath: str) -> str:
    """
    Read and return the contents of a policy XML file.

    Args:
        policy_xml_filepath (str): Path to the policy XML file.

    Returns:
        str: Contents of the policy XML file.
    """

    # Read the specified policy XML file with explicit UTF-8 encoding
    with open(policy_xml_filepath, 'r', encoding = 'utf-8') as policy_xml_file:
        policy_template_xml = policy_xml_file.read()

    return policy_template_xml


# ------------------------------
#    CLASSES
# ------------------------------

class APIMNetworkMode(StrEnum):
    """
    Networking configuration modes for Azure API Management (APIM).
    """

    PUBLIC        = "Public"    # APIM is accessible from the public internet
    EXTERNAL_VNET = "External"  # APIM is deployed in a VNet with external (public) access
    INTERNAL_VNET = "Internal"  # APIM is deployed in a VNet with only internal (private) access
    NONE          = "None"      # No explicit network configuration (legacy or default)


class APIM_SKU(StrEnum):
    """
    APIM SKU types.
    """

    DEVELOPER  = "Developer"
    BASIC      = "Basic"
    STANDARD   = "Standard"
    PREMIUM    = "Premium"
    BASICV2    = "Basicv2"
    STANDARDV2 = "Standardv2"
    PREMIUMV2  = "Premiumv2"


class HTTP_VERB(StrEnum):
    """
    HTTP verbs that can be used for API operations.
    """

    GET     = "GET"
    POST    = "POST"
    PUT     = "PUT"
    DELETE  = "DELETE"
    PATCH   = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD    = "HEAD"


class INFRASTRUCTURE(StrEnum):
    """
    Infrastructure types for APIM automation scenarios.
    """

    SIMPLE_APIM  = "simple-apim"   # Simple API Management with no dependencies
    APIM_ACA     = "apim-aca"      # Azure API Management connected to Azure Container Apps
    AFD_APIM_PE  = "afd-apim-pe"   # Azure Front Door Premium connected to Azure API Management (Standard V2) via Private Link


# ------------------------------
#    CLASSES
# ------------------------------

@dataclass
class API:
    """
    Represents an API definition within API Management.
    """

    name: str
    displayName: str
    path: str
    description: str
    policyXml: Optional[str] = None
    operations: Optional[List['APIOperation']] = None
    tags: Optional[List[str]] = None
    productNames: Optional[List[str]] = None
    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, name: str, displayName: str, path: str, description: str, policyXml: Optional[str] = None, operations: Optional[List['APIOperation']] = None, tags: Optional[List[str]] = None, productNames: Optional[List[str]] = None):
        self.name = name
        self.displayName = displayName
        self.path = path
        self.description = description
        self.policyXml = policyXml if policyXml is not None else _read_policy_xml(DEFAULT_XML_POLICY_PATH)
        self.operations = operations if operations is not None else []
        self.tags = tags if tags is not None else []
        self.productNames = productNames if productNames is not None else []
    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def to_dict(self) -> dict:
        api_dict = {
            "name": self.name,
            "displayName": self.displayName,
            "path": self.path,
            "description": self.description,
            "operations": [op.to_dict() for op in self.operations] if self.operations else []
        }

        if self.policyXml is not None:
            api_dict["policyXml"] = self.policyXml

        if self.tags:
            api_dict["tags"] = self.tags

        if self.productNames:
            api_dict["productNames"] = self.productNames

        return api_dict


@dataclass
class APIOperation:
    """
    Represents an operation for a specific HTTP method within a parent API.
    """

    name: str
    displayName: str
    urlTemplate: str
    method: HTTP_VERB
    description: str
    policyXml: str


    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, name: str, displayName: str, urlTemplate: str, method: HTTP_VERB, description: str, policyXml: Optional[str] = None):
        # Validate that method is a valid HTTP_VERB
        if not isinstance(method, HTTP_VERB):
            try:
                method = HTTP_VERB(method)
            except Exception:
                raise ValueError(f"Invalid HTTP_VERB: {method}")

        self.name = name
        self.displayName = displayName
        self.method = method
        self.urlTemplate = urlTemplate
        self.description = description
        self.policyXml = policyXml if policyXml is not None else _read_policy_xml(DEFAULT_XML_POLICY_PATH)


    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "displayName": self.displayName,
            "urlTemplate": self.urlTemplate,
            "description": self.description,
            "method": self.method,
            "policyXml": self.policyXml,
        }


@dataclass
class GET_APIOperation(APIOperation):
    """
    Represents a simple GET operation within a parent API.
    """


    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, description: str, policyXml: Optional[str] = None):
        super().__init__('GET', 'GET', '/', HTTP_VERB.GET, description, policyXml)


@dataclass
class POST_APIOperation(APIOperation):
    """
    Represents a simple POST operation within a parent API.
    """


    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, description: str, policyXml: Optional[str] = None):
        super().__init__('POST', 'POST', '/', HTTP_VERB.POST, description, policyXml)


@dataclass
class NamedValue:
    """
    Represents a named value within API Management.
    """

    name: str
    value: str
    isSecret: bool = False

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, name: str, value: str, isSecret: bool = False):
        self.name = name
        self.value = value
        self.isSecret = isSecret


    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def to_dict(self) -> dict:
        nv_dict = {
            "name": self.name,
            "value": self.value,
            "isSecret": self.isSecret
        }

        return nv_dict
    
@dataclass
class PolicyFragment:
    """
    Represents a policy fragment within API Management.
    """

    name: str
    policyXml: str
    description: str

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, name: str, policyXml: str, description: str = ''):
        self.name = name
        self.policyXml = policyXml
        self.description = description


    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def to_dict(self) -> dict:
        pf_dict = {
            "name": self.name,
            "policyXml": self.policyXml,
            "description": self.description 
        }

        return pf_dict


@dataclass
class Product:
    """
    Represents a Product definition within API Management.
    Products in APIM are logical groupings of APIs with associated policies,
    terms of use, and rate limits. They are used to manage API access control.
    """
    
    name: str
    displayName: str
    description: str
    state: str = 'published'  # 'published' or 'notPublished'
    subscriptionRequired: bool = True
    approvalRequired: bool = False
    policyXml: Optional[str] = None
    
    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------
    
    def __init__(self, name: str, displayName: str, description: str, state: str = 'published', subscriptionRequired: bool = True, approvalRequired: bool = False, policyXml: Optional[str] = None):
        self.name = name
        self.displayName = displayName
        self.description = description
        self.state = state
        self.subscriptionRequired = subscriptionRequired
        self.approvalRequired = approvalRequired
        # Only try to read default policy if policyXml is None and we're not in a test environment
        if policyXml is None:
            try:
                self.policyXml = _read_policy_xml(DEFAULT_XML_POLICY_PATH)
            except FileNotFoundError:
                # Fallback to a simple default policy for testing or when file is not found
                self.policyXml = """<policies>
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
        else:
            self.policyXml = policyXml
    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def to_dict(self) -> dict:
        product_dict = {
            "name": self.name,
            "displayName": self.displayName,
            "description": self.description,
            "state": self.state,
            "subscriptionRequired": self.subscriptionRequired,
            "approvalRequired": self.approvalRequired
        }

        if self.policyXml is not None:
            product_dict["policyXml"] = self.policyXml

        return product_dict