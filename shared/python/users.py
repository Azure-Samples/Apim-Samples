"""
Types and constants for authentication and authorization.
"""

from typing import List
from enum import StrEnum
import random
from apimtypes import Role


# ------------------------------
#    CLASSES
# ------------------------------

class UserName(StrEnum):
    """
    Predefined user names for testing purposes.
    """

    DYLAN_WILLIAMS = 'Dylan Williams'
    ELIZABETH_MOORE = 'Elizabeth Moore'
    MARIO_ROGERS = 'Mario Rogers'
    ELLIS_TURNER = 'Ellis Turner'
    HARRY_SMITH = 'Harry Smith'


class User:
    """
    Represents a user and their roles.
    """

    # ------------------------------
    #    CONSTRUCTOR
    # ------------------------------

    def __init__(self, user_id: str, name: str, roles: list[str] = None) -> None:
        """
        Initializes a User instance with a unique ID, name, and roles.

        Args:
            user_id (str): The user's unique ID.
            name (str): The user's name.
            roles (list, optional): The user's roles. Defaults to empty list.
        """

        self.id = user_id
        self.name = name
        self.roles = roles if roles is not None else []


    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    def __repr__(self) -> str:
        """
        Return a string representation of the User.
        """
        return f"User(id='{self.id}', name='{self.name}', roles={self.roles})"


# ------------------------------
#    CONSTANTS
# ------------------------------

# Predefined users
Users: List[User] = [
    User('4ea76b2c-6cea-4b8f-b81e-b242ae10c040', UserName.DYLAN_WILLIAMS),
    User('e461f19b-4795-4153-a0c4-77e4561b1d0e', UserName.ELIZABETH_MOORE, [Role.HR_MEMBER]),
    User('5b873099-8d4b-4563-846e-6c591e660a8f', UserName.MARIO_ROGERS, [Role.HR_MEMBER, Role.HR_ASSOCIATE]),
    User('236af317-ef1e-4a37-918a-f58f51ce421a', UserName.ELLIS_TURNER, [Role.HR_MEMBER, Role.HR_ADMINISTRATOR]),
    User('d1f8b2c3-4e5f-6a7b-8c9d-e0f1a2b3c4d5', UserName.HARRY_SMITH, [Role.MARKETING_MEMBER])
]

class UserHelper:
    """
    Static helper class for user-related operations.
    """

    # ------------------------------
    #    PUBLIC METHODS
    # ------------------------------

    @staticmethod
    def get_user(username: 'str | UserName') -> 'User | None':
        """
        Retrieves a user by their username (string or UserName enum).

        Args:
            username (str | UserName): The user's name as a string or UserName enum value.

        Returns:
            User | None: The user if found, otherwise None.
        """

        name = username.value if hasattr(username, 'value') else username

        return next((user for user in Users if user.name == name), None)

    @staticmethod
    def get_user_by_role(role_or_roles: str | list[str]) -> 'User | None':
        """
        Retrieves a random user who has any of the specified roles.

        If Role.NONE is provided (as a single role or in a list), returns a user with no roles attached.

        Args:
            role_or_roles (str | list[str]): A single role string or a list of role strings from the Role enum.

        Returns:
            User | None: A random user with one of the given roles, or a user with no roles if Role.NONE is specified, or None if no match.
        """

        if isinstance(role_or_roles, str):
            roles = [role_or_roles]
        else:
            roles = role_or_roles

        if Role.NONE in roles:
            # Return a user with no roles attached
            users_with_no_roles = [user for user in Users if not user.roles]
            if not users_with_no_roles:
                return None

            return random.choice(users_with_no_roles)

        matching_users = [user for user in Users if any(r in roles for r in user.roles)]

        if not matching_users:
            return None

        return random.choice(matching_users)
