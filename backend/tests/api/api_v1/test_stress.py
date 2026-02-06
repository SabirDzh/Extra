import pytest
from httpx import AsyncClient

# Test scenarios designed to stress test input validation and controller handling

@pytest.mark.anyio
async def test_register_user_with_emojis(client: AsyncClient):
    """Test registration with emojis in text fields. Should be handled gracefully (accepted or rejected properly), not 500."""
    payload = {
        "email": "emoji_user@example.com",
        "password": "password12345",
        "role": "user",
        "username": {
            "first_name": "😊User🚀",
            "last_name": "Tεst",
            "middle_name": "🤷‍♂️"
        },
        "is_active": True,
        "is_superuser": False,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # It depends on validation rules. If no regex is enforced, this should likely succeed (201)
    # If it fails with 422 (Validation Error), that is also acceptable.
    # It MUST NOT be 500.
    assert response.status_code in [201, 422], f"Unexpected status code: {response.status_code}, Response: {response.text}"
    
    if response.status_code == 201:
        data = response.json()
        assert data["username"]["first_name"] == "😊User🚀"

@pytest.mark.anyio
async def test_register_user_with_huge_input(client: AsyncClient):
    """Test registration with input exceeding max length."""
    huge_string = "a" * 1000  # Schema max is 128
    payload = {
        "email": "huge_input@example.com",
        "password": "password12345",
        "role": "user",
        "username": {
            "first_name": huge_string
        },
        "is_active": True,
        "is_superuser": False,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # Should fail validation
    assert response.status_code == 422
    data = response.json()
    # Check that error is about max_length
    assert any("max_length" in str(err) for err in data.get("detail", []))

@pytest.mark.anyio
async def test_register_user_sql_injection_payload(client: AsyncClient):
    """Test registration with SQL injection payloads. Pydantic/ORM should sanitize this."""
    payload = {
        "email": "sql_inject@example.com",
        "password": "password12345",
        "role": "user",
        "username": {
            "first_name": "Robert'); DROP TABLE users; --"
        },
        "is_active": True,
        "is_superuser": False,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # Should succeed as a literal string (201) and NOT execute SQL.
    # OR fail validation if specific chars are forbidden (422).
    # MUST NOT be 500.
    assert response.status_code in [201, 422]
    
    if response.status_code == 201:
        data = response.json()
        assert data["username"]["first_name"] == "Robert'); DROP TABLE users; --"

@pytest.mark.anyio
async def test_register_user_xss_payload(client: AsyncClient):
    """Test registration with XSS payloads."""
    payload = {
        "email": "xss@example.com",
        "password": "password12345",
        "role": "user",
        "username": {
            "first_name": "<script>alert('XSS')</script>"
        },
        "is_active": True,
        "is_superuser": False,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # API usually stores as is. Frontend is responsible for escaping.
    assert response.status_code in [201, 422]
    if response.status_code == 201:
        data = response.json()
        assert data["username"]["first_name"] == "<script>alert('XSS')</script>"

@pytest.mark.anyio
async def test_register_invalid_email_format(client: AsyncClient):
    """Test registration with invalid email format."""
    payload = {
        "email": "not-an-email",
        "password": "password12345",
        "role": "user",
        "username": {
            "first_name": "User"
        },
        "is_active": True,
        "is_superuser": False,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # Should fail validation
    assert response.status_code == 422
    data = response.json()
    assert any("value is not a valid email address" in str(err["msg"]) for err in data.get("detail", []))

@pytest.mark.anyio
async def test_register_invalid_role(client: AsyncClient):
    """Test registration with a role that is not in the Enum."""
    payload = {
        "email": "bad_role@example.com",
        "password": "password12345",
        "role": "god_emperor",
        "username": {
            "first_name": "User"
        },
        "is_active": True,
        "is_superuser": False,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # Should fail validation
    assert response.status_code == 422
    data = response.json()
    # Pydantic enum validation error
    assert any("Input should be 'user', 'administrator', 'manager' or 'client'" in str(err["msg"]) for err in data.get("detail", []))

@pytest.mark.anyio
async def test_register_empty_first_name(client: AsyncClient):
    """Test registration with empty first name string."""
    payload = {
        "email": "empty_name@example.com",
        "password": "password12345",
        "role": "user",
        "username": {
            "first_name": ""
        },
        "is_active": True,
        "is_superuser": False,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # Should fail validation (min_length=1)
    assert response.status_code == 422
    data = response.json()
    assert any("String should have at least 1 character" in str(err["msg"]) for err in data.get("detail", []))
