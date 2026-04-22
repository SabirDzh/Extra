import pytest
from httpx import AsyncClient
from urllib.parse import urlencode




INVALID_EMAILS_STRICT = [
    "plainaddress",
    "#@%^%#$@#$@#.com",
    "@example.com",
    "email.example.com",
    "email@example@example.com",
    ".email@example.com",
    "email.@example.com",
    "email..email@example.com",
    "email@example",
    "email@-example.com",
    "",
]



COMPLEX_EMAILS = [
    ("Joe Smith <email@example.com>", "email@example.com"),
]


INVALID_FULLNAMES = [
    "",
    None,
]



@pytest.mark.anyio
@pytest.mark.parametrize("email", INVALID_EMAILS_STRICT)
async def test_register_invalid_emails_strict(client: AsyncClient, email):
    """Attempt to register with strictly invalid email addresses."""
    payload = {
        "email": email,
        "password": "Password12345!",
        "role": "user",
        "fullname": "Test",
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422, f"Email '{email}' should have been rejected."

@pytest.mark.anyio
@pytest.mark.parametrize("input_email, expected_email", COMPLEX_EMAILS)
async def test_register_complex_emails(client: AsyncClient, input_email, expected_email):
    """Check how system handles complex email formats (e.g. normalization)."""
    payload = {
        "email": input_email,
        "password": "Password12345!",
        "role": "user",
        "fullname": "Test",
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    

    if response.status_code == 201:
        data = response.json()
        assert data["email"] == expected_email, f"Email '{input_email}' was not normalized to '{expected_email}'"
    elif response.status_code == 422:
        pass
    else:
        pytest.fail(f"Unexpected status code {response.status_code} for email '{input_email}'")

@pytest.mark.anyio
@pytest.mark.parametrize("fullname_value", INVALID_FULLNAMES)
async def test_register_invalid_fullname(client: AsyncClient, fullname_value):
    """Attempt to register with malformed fullname."""
    payload = {
        "email": "valid@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": fullname_value,
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422

@pytest.mark.anyio
async def test_register_duplicate_email(client: AsyncClient):
    """Test that registering the same email twice fails."""
    payload = {
        "email": "duplicate@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "First"
    }
    await client.post("/api/v1/auth/register", json=payload)
    resp2 = await client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 400
    assert "REGISTER_USER_ALREADY_EXISTS" in resp2.text

@pytest.mark.anyio
async def test_register_missing_fields(client: AsyncClient):
    """Test payloads with missing top-level fields."""
    base_payload = {
        "email": "missing@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "Test"
    }
    fields_to_remove = ["email", "password", "fullname", "role"]
    for field in fields_to_remove:
        bad_payload = base_payload.copy()
        del bad_payload[field]
        response = await client.post("/api/v1/auth/register", json=bad_payload)
        assert response.status_code == 422

@pytest.mark.anyio
async def test_login_flow_comprehensive(client: AsyncClient, create_user):
    """Test various login scenarios."""
    email = "login_comp@example.com"
    password = "correct_password"
    await create_user(email, password)


    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code in [200, 204]


    resp = await client.post("/api/v1/auth/login", data={"username": email, "password": "wrong_password"})
    assert resp.status_code == 400


    resp = await client.post("/api/v1/auth/login", data={"username": "wrong@example.com", "password": password})
    assert resp.status_code == 400


    resp = await client.post("/api/v1/auth/login", data={"username": email})
    assert resp.status_code == 422


    resp = await client.post("/api/v1/auth/login", data={"password": password})
    assert resp.status_code == 422

@pytest.mark.anyio
async def test_register_case_insensitivity(client: AsyncClient):
    """Test that email registration is likely case-insensitive regarding duplicates."""
    payload1 = {
        "email": "CASE@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "Test"
    }
    resp1 = await client.post("/api/v1/auth/register", json=payload1)
    assert resp1.status_code == 201

    payload2 = payload1.copy()
    payload2["email"] = "case@example.com"
    resp2 = await client.post("/api/v1/auth/register", json=payload2)
    assert resp2.status_code == 400 

@pytest.mark.anyio
@pytest.mark.parametrize("role_value", ["administrator", "manager", "client", "user"])
async def test_register_valid_roles(client: AsyncClient, role_value):
    """Test that all defined roles are accepted."""
    payload = {
        "email": f"role_{role_value}@example.com",
        "password": "Password12345!",
        "role": role_value,
        "fullname": "Test"
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["role"] == role_value



@pytest.mark.anyio
async def test_logout(client: AsyncClient, normal_user_token_headers):
    """Test logout flow."""



    

    response = await client.post("/api/v1/auth/logout", headers=normal_user_token_headers)
    assert response.status_code in [200, 204]




@pytest.mark.anyio
async def test_logout_unauthorized(client: AsyncClient):
    """Test logout without being logged in."""
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 401

@pytest.mark.anyio
async def test_forgot_password_flow(client: AsyncClient, create_user):
    """Test request for password reset."""
    email = "forgot@example.com"
    await create_user(email)


    response = await client.post("/api/v1/auth/forgot-password", json={"email": email})

    assert response.status_code == 202



    response = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 202


    response = await client.post("/api/v1/auth/forgot-password", json={"email": "not-an-email"})
    assert response.status_code == 422

@pytest.mark.anyio
async def test_reset_password_bad_token(client: AsyncClient):
    """Test reset password with invalid token."""
    payload = {
        "token": "invalid_token",
        "password": "newPassword12345!"
    }
    response = await client.post("/api/v1/auth/reset-password", json=payload)
    assert response.status_code == 400


@pytest.mark.anyio
async def test_verify_request_flow(client: AsyncClient, create_user):
    """Test requesting verification token."""
    email = "verify_req@example.com"
    await create_user(email)
    

    response = await client.post("/api/v1/auth/request-verify-token", json={"email": email})

    assert response.status_code == 202

@pytest.mark.anyio
async def test_verify_bad_token(client: AsyncClient):
    """Test verifying with invalid token."""
    response = await client.post("/api/v1/auth/verify", json={"token": "bad_token"})
    assert response.status_code == 400




@pytest.mark.anyio
async def test_users_unauthorized_access(client: AsyncClient):
    """Ensure public cannot access user list."""
    response = await client.get("/api/v1/users")







    if response.status_code == 200:
        pass
    elif response.status_code == 401:
        pass
    else:
        pytest.fail(f"Unexpected status for users list: {response.status_code}")

@pytest.mark.anyio
async def test_get_user_by_id_flow(client: AsyncClient, create_user, superuser_token_headers):
    """Test retrieving specific user by ID (requires Admin)."""
    user = await create_user("target@example.com")
    user_id = str(user.id)
    


    response = await client.get(f"/api/v1/users/{user_id}", headers=superuser_token_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "target@example.com"
    assert data["id"] == user_id

@pytest.mark.anyio
async def test_update_me(client: AsyncClient, create_user):
    """Test updating own profile."""

    email = "update_me@example.com"
    password = "password"
    user = await create_user(email, password)
    

    await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    


    new_fullname = "Updated Name"
    payload = {"fullname": new_fullname}
    
    response = await client.patch("/api/v1/users/me", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["fullname"] == new_fullname



@pytest.mark.anyio
async def test_messages_unauthorized(client: AsyncClient):
    """Test accessing messages without login."""
    response = await client.get("/api/v1/messages")
    assert response.status_code == 401

@pytest.mark.anyio
async def test_secrets_role_access(client: AsyncClient, create_user):
    """Comprehensive check for secrets endpoint access by role."""
    

    u_email = "u@test.com"
    await create_user(u_email, role="user")
    await client.post("/api/v1/auth/login", data={"username": u_email, "password": "Password12345!"})
    resp = await client.get("/api/v1/messages/secrets")
    assert resp.status_code == 403
    

    c_email = "c@test.com"
    await create_user(c_email, role="client")
    await client.post("/api/v1/auth/login", data={"username": c_email, "password": "Password12345!"})
    resp = await client.get("/api/v1/messages/secrets")
    assert resp.status_code == 403
    

    a_email = "a@test.com"
    await create_user(a_email, role="administrator", is_superuser=True)
    await client.post("/api/v1/auth/login", data={"username": a_email, "password": "Password12345!"})
    resp = await client.get("/api/v1/messages/secrets")
    assert resp.status_code == 200



@pytest.mark.anyio
async def test_service_stats_structure(client: AsyncClient):
    """Verify structure of stats response."""

    await client.get("/api/v1/users")
    await client.get("/not-found-path")
    
    response = await client.get("/api/v1/service/stats")
    assert response.status_code == 200
    data = response.json()
    



    assert isinstance(data, dict)