"""
Factory for creating authentication tokens or objects for Azure API Management samples.
"""

from typing import Any
import time
import jwt

# APIM Samples imports
from users import User

# ------------------------------
#    CLASSES
# ------------------------------

class JwtPayload:
    """
    Represents the payload (claims) of a JSON Web Token for APIM testing.
    https://datatracker.ietf.org/doc/html/rfc7519
    """

    # ------------------------------
    #    CONSTANTS
    # ------------------------------

    DEFAULT_LIFETIME_SECONDS = 3600 * 24  # Default lifetime of 24 hours


    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, subject: str, name: str, issued_at: int | None = None, expires: int | None = None, roles: dict[str] | None = None) -> None:
        self.sub = subject
        self.name = name
        self.iat = issued_at if issued_at is not None else int(time.time())
        self.exp = expires if expires is not None else self.iat + self.DEFAULT_LIFETIME_SECONDS
        self.roles = roles if roles is not None else []


    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the payload to a dictionary for encoding.
        """
        pl: dict[str, Any] = {
            'sub': self.sub,
            'name': self.name,
            'iat': self.iat,
            'exp': self.exp
        }

        if bool(self.roles):
            pl['roles'] = self.roles

        return pl


class SymmetricJwtToken:
    """
    Represents a JSON Web Token using a symmetric signing algorithm (HS256) for APIM testing.
    This is a simple implementation for demonstration purposes as it uses a shared secret key
    for the token creation and verification. This is not production-ready code.
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, key: str, payload: JwtPayload) -> None:
        """
        Initialize the SymmetricJwtToken with a signing key and payload.

        Args:
            key (str): The symmetric key as a regular ASCII string. This should NOT be a base64-encoded string. Use the raw ASCII string that will be used for signing the JWT. If you have a base64-encoded key, decode it to its ASCII form before passing it here.
            payload (JwtPayload): The payload (claims) for the JWT.
        """
        self.key = key
        self.payload = payload


    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def encode(self) -> str:
        """
        Encode the JWT token using the provided key and payload.

        Returns:
            str: The encoded JWT as a string.

        Note:
            The key parameter used for signing must be a regular ASCII string, NOT a base64-encoded string. If you have a base64-encoded key, decode it to its ASCII form before using it here. Passing a base64-encoded string directly will result in signature validation errors in APIM or other JWT consumers.
        """
        return jwt.encode(self.payload.to_dict(), self.key, algorithm = 'HS256')


class AuthFactory:
    """
    Factory class for creating authentication tokens or objects.
    """

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    @staticmethod
    def create_symmetric_jwt_token_for_user(user: User, jwt_key: str) -> str:
        if not user:
            raise ValueError('User is required to create a symmetric JWT token.')

        if not str(jwt_key):
            raise ValueError('JWT key is required to create a symmetric JWT token.')

        jwt_payload = JwtPayload(subject = user.id, name = user.name, roles = user.roles)
        symmetric_jwt = SymmetricJwtToken(jwt_key, jwt_payload)

        return symmetric_jwt.encode()

    @staticmethod
    def create_jwt_payload_for_user(user: User) -> Any:
        """
        Create a JWT payload from a User object.

        Args:
            user (User): The user object to create the payload from.

        Returns:
            Any: A dictionary representing the JWT payload.
        """

        if not user:
            raise ValueError('User is required to create JWT payload.')

        return {
            'sub': user.id,
            'name': user.name,
            'roles': user.roles
        }
