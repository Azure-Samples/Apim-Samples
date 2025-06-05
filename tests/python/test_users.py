"""
Unit tests for the User class in users.py.
"""

import pytest
import random
from users import User, Users, UserHelper
from apimtypes import Role

# ------------------------------
#    TESTS
# ------------------------------

@pytest.mark.unit
def test_user_init_with_roles():
    user = User(id="123", name="Alice", roles=["admin", "user"])
    assert user.id == "123"
    assert user.name == "Alice"
    assert user.roles == ["admin", "user"]

@pytest.mark.unit
def test_user_init_without_roles():
    user = User(id="456", name="Bob")
    assert user.id == "456"
    assert user.name == "Bob"
    assert user.roles == []

@pytest.mark.unit
def test_user_role_mutability():
    user = User(id="789", name="Charlie")
    user.roles.append("editor")
    assert user.roles == ["editor"]

@pytest.mark.unit
def test_user_repr():
    user = User(id="abc", name="Dana", roles=["guest"])
    # __repr__ is not defined, so fallback to default, but check type
    assert isinstance(repr(user), str)

"""
Unit tests for User.get_user_by_role in users.py.
"""

# ------------------------------
#    CONSTANTS
# ------------------------------

# No additional constants needed

# ------------------------------
#    VARIABLES
# ------------------------------

# Save and restore Users for test isolation
@pytest.fixture(autouse=True)
def restore_users(monkeypatch):
    original_users = list(Users)
    yield
    Users.clear()
    Users.extend(original_users)

# ------------------------------
#    PRIVATE METHODS
# ------------------------------

def _add_user(id_: str, name: str, roles: list[str]):
    Users.append(User(id_, name, roles))

# ------------------------------
#    PUBLIC METHODS
# ------------------------------

def test_get_user_by_role_single_match():
    """
    Should return a user with the specified single role.
    """
    user = UserHelper.get_user_by_role(Role.HR_MEMBER)
    assert user is not None
    assert Role.HR_MEMBER in user.roles

def test_get_user_by_role_multiple_roles():
    """
    Should return a user with any of the specified roles.
    """
    user = UserHelper.get_user_by_role([Role.HR_MEMBER, Role.HR_ADMINISTRATOR])
    assert user is not None
    assert any(r in [Role.HR_MEMBER, Role.HR_ADMINISTRATOR] for r in user.roles)

def test_get_user_by_role_none_role_returns_user_with_no_roles():
    """
    Should return a user with no roles if Role.NONE is specified.
    """
    # Add a user with no roles for this test
    _add_user('no-role-id', 'NoRoleUser', [])
    user = UserHelper.get_user_by_role(Role.NONE)
    assert user is not None
    assert user.roles == []

def test_get_user_by_role_none_in_list_returns_user_with_no_roles():
    """
    Should return a user with no roles if Role.NONE is in the list.
    """
    _add_user('no-role-id2', 'NoRoleUser2', [])
    user = UserHelper.get_user_by_role([Role.NONE, Role.HR_MEMBER])
    assert user is not None
    assert user.roles == []

def test_get_user_by_role_no_matching_roles_returns_none():
    """
    Should return None if no user matches the given role(s).
    """
    user = UserHelper.get_user_by_role('non-existent-role')
    assert user is None

def test_get_user_by_role_none_role_and_no_user_with_no_roles():
    """
    Should return None if Role.NONE is specified but no user has no roles.
    """
    # Remove all users with no roles
    Users[:] = [u for u in Users if u.roles]
    user = UserHelper.get_user_by_role(Role.NONE)
    assert user is None

def test_get_user_by_role_randomness(monkeypatch):
    """
    Should randomly select among users with the specified role.
    """
    # Add two users with the same role
    _add_user('id1', 'User1', [Role.HR_MEMBER])
    _add_user('id2', 'User2', [Role.HR_MEMBER])
    # Patch random.choice to always return the last user
    monkeypatch.setattr(random, 'choice', lambda seq: seq[-1])
    user = UserHelper.get_user_by_role(Role.HR_MEMBER)
    assert user.name == 'User2'
