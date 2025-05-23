"""
Types and constants for Azure API Management automation and deployment.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


# ------------------------------
#    CONSTANTS
# ------------------------------

# These paths are relative to the infrastructure and samples
SHARED_XML_POLICY_BASE_PATH         = '../../shared/apim-policies'
DEFAULT_XML_POLICY_PATH             = f'{SHARED_XML_POLICY_BASE_PATH}/default.xml'
HELLO_WORLD_XML_POLICY_PATH         = f'{SHARED_XML_POLICY_BASE_PATH}/hello-world.xml'
ACA_BACKEND_1_XML_POLICY_PATH       = f'{SHARED_XML_POLICY_BASE_PATH}/aca-backend-1.xml'
ACA_BACKEND_2_XML_POLICY_PATH       = f'{SHARED_XML_POLICY_BASE_PATH}/aca-backend-2.xml'
ACA_BACKEND_POOL_XML_POLICY_PATH    = f'{SHARED_XML_POLICY_BASE_PATH}/aca-backend-pool.xml'

SUBSCRIPTION_KEY_PARAMETER_NAME = 'api_key'
SLEEP_TIME_BETWEEN_REQUESTS_MS  = 50


# ------------------------------
#    CLASSES
# ------------------------------

class APIMNetworkMode(str, Enum):
    """
    Networking configuration modes for Azure API Management (APIM).
    """

    PUBLIC        = "Public"    # APIM is accessible from the public internet
    EXTERNAL_VNET = "External"  # APIM is deployed in a VNet with external (public) access
    INTERNAL_VNET = "Internal"  # APIM is deployed in a VNet with only internal (private) access
    NONE          = "None"      # No explicit network configuration (legacy or default)


class APIM_SKU(str, Enum):
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


class HTTP_VERB(str, Enum):
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


class INFRASTRUCTURE(str, Enum):
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


    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, name: str, displayName: str, path: str, description: str, policyXml: Optional[str], operations: Optional[List['APIOperation']] = None):
        self.name = name
        self.displayName = displayName
        self.path = path
        self.description = description
        self.policyXml = policyXml if policyXml is not None else None
        self.operations = operations if operations is not None else []


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

    def __init__(self, name: str, displayName: str, urlTemplate: str, method: HTTP_VERB, description: str, policyXml: str):
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
        self.policyXml = policyXml


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

    def __init__(self, description: str, policyXml: str):
        super().__init__('GET', 'GET', '/', HTTP_VERB.GET, description, policyXml)


@dataclass
class POST_APIOperation(APIOperation):
    """
    Represents a simple POST operation within a parent API.
    """


    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, description: str, policyXml: str):
        super().__init__('POST', 'POST', '/', HTTP_VERB.POST, description, policyXml)