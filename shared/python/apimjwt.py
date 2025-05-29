"""
Module for creating JSON Web Tokens (JWT) used with API Management requests.
"""

import jwt
import time
from typing import Any, Dict


# ------------------------------
#    CLASSES
# ------------------------------

class JwtPayload:
    """
    Represents the payload (claims) of a JSON Web Token for APIM testing.
    https://datatracker.ietf.org/doc/html/rfc7519
    """

    DEFAULT_LIFETIME_SECONDS = 3600 * 24  # Default lifetime of 24 hours

    def __init__(self, subject: str, name: str, issued_at: int | None = None, expires: int | None = None) -> None:
        self.sub = subject
        self.name = name        
        self.iat = issued_at if issued_at is not None else int(time.time())
        self.exp = expires if expires is not None else self.iat + self.DEFAULT_LIFETIME_SECONDS

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the payload to a dictionary for encoding.
        """
        return {
            "sub": self.sub,
            "name": self.name,
            "iat": self.iat,
            "exp": self.exp
        }

class SymmetricJwtToken:
    """
    Represents a JSON Web Token using a symmetric signing algorithm (HS256) for APIM testing.
    This is a simple implementation for demonstration purposes as it uses a shared secret key
    for the token creation and verification. This is not production-ready code.
    """

    def __init__(self, key: str, payload: JwtPayload) -> None:
        """
        Initialize the SymmetricJwtToken with a signing key and payload.

        Args:
            key (str): The symmetric key as a regular ASCII string. This should NOT be a base64-encoded string. Use the raw ASCII string that will be used for signing the JWT. If you have a base64-encoded key, decode it to its ASCII form before passing it here.
            payload (JwtPayload): The payload (claims) for the JWT.
        """
        self.key = key
        self.payload = payload

    def encode(self) -> str:
        """
        Encode the JWT token using the provided key and payload.

        Returns:
            str: The encoded JWT as a string.

        Note:
            The key parameter used for signing must be a regular ASCII string, NOT a base64-encoded string. If you have a base64-encoded key, decode it to its ASCII form before using it here. Passing a base64-encoded string directly will result in signature validation errors in APIM or other JWT consumers.
        """
        return jwt.encode(self.payload.to_dict(), self.key, algorithm = "HS256")