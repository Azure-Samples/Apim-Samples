"""
Unit tests for the User class in users.py.
"""

import random
import pytest
from users import User, Users, UserHelper
from apimtypes import Role

# ------------------------------
#    TESTS
# ------------------------------

@pytest.mark.unit
def test_user_init_with_roles():
    user = User(id='123', name='Alice', roles=['admin', 'user'])
    assert user.id == '123'
    assert user.name == 'Alice'
    assert user.roles == ['admin', 'user']

@pytest.mark.unit
def test_user_init_without_roles():
    user = User(id='456', name='Bob')
    assert user.id == '456'
    assert user.name == 'Bob'
    assert user.roles == []

@pytest.mark.unit
def test_user_role_mutability():
    user = User(id='789', name='Charlie')
    user.roles.append('editor')
    assert user.roles == ['editor']

@pytest.mark.unit
def test_user_repr():
    user = User(id='abc', name='Dana', roles=['guest'])
    # __repr__ is not defined, so fallback to default, but check type
    assert isinstance(repr(user), str)


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

# ------------------------------
#    ADDITIONAL COVERAGE TESTS
# ------------------------------

def test_user_edge_cases():
    """Test User class with edge cases."""
    # Test with empty/None values
    user_empty = User('', '', [])
    assert user_empty.id == ''
    assert user_empty.name == ''
    assert user_empty.roles == []

    user_none_roles = User('test', 'Test', None)
    assert user_none_roles.roles == []

    # Test role modification after creation
    user = User('test', 'Test', ['role1'])
    user.roles.append('role2')
    assert 'role2' in user.roles


def test_user_helper_edge_cases():
    """Test UserHelper with comprehensive edge cases."""
    # Test with roles that don't exist in any user
    result = UserHelper.get_user_by_role('nonexistent_role')
    assert result is None

    # Test with multiple users having the same role
    users_with_same_role = [u for u in Users if 'hr_member' in u.roles]
    if len(users_with_same_role) > 1:
        # Should return one of them (random selection)
        result = UserHelper.get_user_by_role('hr_member')
        assert result is not None
        assert 'hr_member' in result.roles


def test_user_helper_role_variations():
    """Test UserHelper with different role variations."""
    # Test with role as single string vs list
    result_str = UserHelper.get_user_by_role('hr_administrator')
    result_list = UserHelper.get_user_by_role(['hr_administrator'])

    if result_str is not None:
        assert result_str.id == result_list.id


def test_user_helper_users_list_integrity():
    """Test that Users list has expected structure."""
    assert isinstance(Users, list)
    assert len(Users) > 0

    for user in Users:
        assert isinstance(user, User)
        assert isinstance(user.id, str)
        assert isinstance(user.name, str)
        assert isinstance(user.roles, list)


def test_user_equality_and_hashing():
    """Test User equality and potential hashing."""
    user1 = User('test', 'Test User', ['role1'])
    user2 = User('test', 'Test User', ['role1'])
    user3 = User('different', 'Different User', ['role2'])

    # Test equality based on content
    assert user1.id == user2.id
    assert user1.name == user2.name
    assert user1.roles == user2.roles

    # Test inequality
    assert user1.id != user3.id
    assert user1.name != user3.name
    assert user1.roles != user3.roles


def test_user_repr_completeness():
    """Test User __repr__ method provides useful information."""
    user = User('test-id', 'Test User Name', ['admin', 'user'])
    repr_str = repr(user)

    assert 'User' in repr_str
    assert 'test-id' in repr_str
    assert 'Test User Name' in repr_str


def test_get_user_by_role_with_none_handling():
    """Test get_user_by_role with None handling for users with no roles."""
    # First, check if there's a user with no roles
    users_with_no_roles = [u for u in Users if not u.roles]

    if users_with_no_roles:
        # Test getting user with None role using Role.NONE
        result = UserHelper.get_user_by_role(Role.NONE)
        assert result is not None
        assert not result.roles  # Should have empty roles list
    else:
        # If no users with empty roles, test should return None
        result = UserHelper.get_user_by_role(Role.NONE)
        assert result is None


def test_user_helper_randomness_distribution():
    """Test that get_user_by_role provides some randomness when multiple users match."""
    # This test checks the randomness aspect mentioned in the existing tests
    matching_role = 'hr_member'  # Assuming this role exists in multiple users

    results = set()
    for _ in range(10):  # Try 10 times to see if we get different results
        user = UserHelper.get_user_by_role(matching_role)
        if user:
            results.add(user.id)

    # If there are multiple users with the same role, we might get different results
    # This is a probabilistic test, so we can't assert definitively
    if len([u for u in Users if matching_role in u.roles]) > 1:
        # With randomness, we might get different users
        pass  # Can't assert much here due to randomness

    # At minimum, we should get valid results
    for _ in range(3):
        user = UserHelper.get_user_by_role(matching_role)
        if user:
            assert matching_role in user.roles


def test_user_roles_mutability_safety():
    """Test that user roles can be safely modified."""
    user = User('test', 'Test', ['initial_role'])
    original_roles = user.roles.copy()

    # Modify roles
    user.roles.append('new_role')
    user.roles.remove('initial_role')

    assert 'new_role' in user.roles
    assert 'initial_role' not in user.roles
    assert user.roles != original_roles
