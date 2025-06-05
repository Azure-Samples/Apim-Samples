"""
Unit tests for authfactory.py.
"""
import pytest
import time
from authfactory import JwtPayload, SymmetricJwtToken, AuthFactory
from users import User

# ------------------------------
#    CONSTANTS
# ------------------------------

TEST_KEY = "test-secret-key"
TEST_USER = User(id = "u1", name = "Test User", roles = ["role1", "role2"])

# ------------------------------
#    PUBLIC METHODS
# ------------------------------

def test_jwt_payload_to_dict_includes_roles():
    payload = JwtPayload(subject = "subj", name = "Name", roles = ["r1", "r2"])
    d = payload.to_dict()
    assert d["sub"] == "subj"
    assert d["name"] == "Name"
    assert d["roles"] == ["r1", "r2"]
    assert "iat" in d and "exp" in d

def test_jwt_payload_to_dict_excludes_empty_roles():
    payload = JwtPayload(subject = "subj", name = "Name", roles = [])
    d = payload.to_dict()
    assert "roles" not in d

def test_symmetric_jwt_token_encode():
    payload = JwtPayload(subject = "subj", name = "Name", roles = ["r1"])
    token = SymmetricJwtToken(TEST_KEY, payload).encode()
    assert isinstance(token, str)
    assert token.count(".") == 2  # JWT has 3 parts

def test_create_symmetric_jwt_token_for_user_success():
    token = AuthFactory.create_symmetric_jwt_token_for_user(TEST_USER, TEST_KEY)
    assert isinstance(token, str)
    assert token.count(".") == 2

def test_create_symmetric_jwt_token_for_user_no_user():
    with pytest.raises(ValueError):
        AuthFactory.create_symmetric_jwt_token_for_user(None, TEST_KEY)

def test_create_symmetric_jwt_token_for_user_no_key():
    with pytest.raises(ValueError):
        AuthFactory.create_symmetric_jwt_token_for_user(TEST_USER, "")

def test_create_jwt_payload_for_user_no_user():
    with pytest.raises(ValueError):
        AuthFactory.create_jwt_payload_for_user(None)
