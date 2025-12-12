"""
Unit tests for authfactory.py.
"""
import time
import pytest

# APIM Samples imports
from authfactory import JwtPayload, SymmetricJwtToken, AuthFactory
from users import User

# ------------------------------
#    CONSTANTS
# ------------------------------

TEST_KEY = 'test-secret-key'
TEST_USER = User(user_id = 'u1', name = 'Test User', roles = ['role1', 'role2'])

# ------------------------------
#    PUBLIC METHODS
# ------------------------------

def test_jwt_payload_to_dict_includes_roles():
    payload = JwtPayload(subject = 'subj', name = 'Name', roles = ['r1', 'r2'])
    d = payload.to_dict()
    assert d['sub'] == 'subj'
    assert d['name'] == 'Name'
    assert d['roles'] == ['r1', 'r2']
    assert 'iat' in d and 'exp' in d

def test_jwt_payload_to_dict_excludes_empty_roles():
    payload = JwtPayload(subject = 'subj', name = 'Name', roles = [])
    d = payload.to_dict()
    assert 'roles' not in d

def test_symmetric_jwt_token_encode():
    payload = JwtPayload(subject = 'subj', name = 'Name', roles = ['r1'])
    token = SymmetricJwtToken(TEST_KEY, payload).encode()
    assert isinstance(token, str)
    assert token.count('.') == 2  # JWT has 3 parts

def test_create_symmetric_jwt_token_for_user_success():
    token = AuthFactory.create_symmetric_jwt_token_for_user(TEST_USER, TEST_KEY)
    assert isinstance(token, str)
    assert token.count('.') == 2

def test_create_symmetric_jwt_token_for_user_no_user():
    with pytest.raises(ValueError):
        AuthFactory.create_symmetric_jwt_token_for_user(None, TEST_KEY)

def test_create_symmetric_jwt_token_for_user_no_key():
    with pytest.raises(ValueError):
        AuthFactory.create_symmetric_jwt_token_for_user(TEST_USER, '')

def test_create_jwt_payload_for_user_no_user():
    with pytest.raises(ValueError):
        AuthFactory.create_jwt_payload_for_user(None)

# ------------------------------
#    ADDITIONAL COVERAGE TESTS
# ------------------------------

def test_jwt_payload_edge_cases():
    """Test JwtPayload with edge cases."""

    # Test with empty roles
    payload = JwtPayload('test-user', 'Test User', roles=[])
    payload_dict = payload.to_dict()
    assert 'roles' not in payload_dict  # Empty roles should be excluded
    assert payload_dict['sub'] == 'test-user'
    assert payload_dict['name'] == 'Test User'
    assert 'iat' in payload_dict
    assert 'exp' in payload_dict

    # Test with None roles
    payload_none = JwtPayload('test-user', 'Test User', roles=None)
    payload_dict_none = payload_none.to_dict()
    assert 'roles' not in payload_dict_none

    # Test expiration time
    current_time = int(time.time())
    payload = JwtPayload('test', 'Test', roles=['role1'])
    payload_dict = payload.to_dict()
    # Should expire in about 24 hours (86400 seconds)
    assert payload_dict['exp'] > current_time + 86300
    assert payload_dict['exp'] < current_time + 86500


def test_symmetric_jwt_token_edge_cases():
    """Test SymmetricJwtToken with edge cases."""
    # Test with valid payload and different keys
    payload = JwtPayload('test', 'Test', roles=['role1'])

    # Test that different keys produce different tokens
    token1 = SymmetricJwtToken('key1', payload)
    token2 = SymmetricJwtToken('key2', payload)

    encoded1 = token1.encode()
    encoded2 = token2.encode()

    assert encoded1 != encoded2  # Different keys should produce different tokens
    assert isinstance(encoded1, str)
    assert isinstance(encoded2, str)

    # Test with same key should produce same token
    token3 = SymmetricJwtToken('key1', payload)
    encoded3 = token3.encode()
    assert encoded1 == encoded3


def test_auth_factory_edge_cases():
    """Test AuthFactory with various edge cases."""
    user = User('test', 'Test User', ['role1', 'role2'])

    # Test with empty key
    with pytest.raises(ValueError):
        AuthFactory.create_symmetric_jwt_token_for_user(user, '')

    # Test with None user
    with pytest.raises(ValueError):
        AuthFactory.create_symmetric_jwt_token_for_user(None, 'test-key')


def test_create_jwt_payload_for_user():
    """Test create_jwt_payload_for_user method."""
    user = User('test-id', 'Test User', ['admin', 'user'])

    payload = AuthFactory.create_jwt_payload_for_user(user)
    assert payload['sub'] == 'test-id'
    assert payload['name'] == 'Test User'
    assert payload['roles'] == ['admin', 'user']

    # Test with None user
    with pytest.raises(ValueError):
        AuthFactory.create_jwt_payload_for_user(None)


def test_jwt_token_structure():
    """Test that generated JWT tokens have correct structure."""
    user = User('test', 'Test User', ['role1'])
    token = AuthFactory.create_symmetric_jwt_token_for_user(user, 'test-secret-key')

    # JWT should have 3 parts separated by dots
    parts = token.split('.')
    assert len(parts) == 3


def test_jwt_payload_time_handling():
    """Test JwtPayload time handling."""

    before_time = int(time.time())
    payload = JwtPayload('test', 'Test', roles=['role'])
    after_time = int(time.time())

    payload_dict = payload.to_dict()

    # iat should be around current time
    assert payload_dict['iat'] >= before_time
    assert payload_dict['iat'] <= after_time

    # exp should be iat + 86400 (24 hours)
    assert payload_dict['exp'] == payload_dict['iat'] + 86400
