import pytest
from httpx import AsyncClient






TRUNCATION_ATTEMPTS = [
    "admin" + " " * 255 + "x",
    "admin" + "\t" * 100,
]







FORMAT_STRINGS = [
    "%s%s%s%s%s",
    "{0}{0}{0}",
    "{{7*7}}",
    "${7*7}",
]



HOMOGLYPH_EMAIL = "аdmin@example.com" 



@pytest.mark.anyio
@pytest.mark.parametrize("padding", TRUNCATION_ATTEMPTS)
async def test_auth_sql_truncation_attack(client: AsyncClient, padding):
    """
    Attempt to register a user with a very long email/name to cause DB truncation.
    If truncation happens silently, "admin...x" becomes "admin".
    """
    payload = {
        "email": f"truncate_{padding[:50]}@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": padding
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    


    assert response.status_code in [201, 422]
    
    if response.status_code == 201:


        pass

@pytest.mark.anyio
async def test_auth_template_injection_username(client: AsyncClient):
    """
    Attempt Server-Side Template Injection (SSTI) in username.
    If the name is rendered in an email or UI without escaping, this probes for it.
    """
    payload = {
        "email": "ssti@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "{{7*7}}" 
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    

    assert response.status_code == 201
    assert response.json()["fullname"] == "{{7*7}}"

@pytest.mark.anyio
async def test_auth_crlf_injection_email(client: AsyncClient):
    """
    Attempt Email Header Injection (CRLF) in email field.
    Validators usually strictly forbid newlines in email.
    """
    payload = {
        "email": "victim@example.com\r\nBcc: hacker@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "Hacker"
    }
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422

@pytest.mark.anyio
async def test_auth_homoglyph_collision(client: AsyncClient):
    """
    Test registration of homoglyph emails (looks like admin, but isn't).
    Should likely be treated as a valid, distinct user (201) or rejected if IDN policies are strict.
    """
    payload = {
        "email": HOMOGLYPH_EMAIL,
        "password": "Password12345!",
        "role": "user",
        "fullname": "CyrillicUser"
    }
    response = await client.post("/api/v1/auth/register", json=payload)


    assert response.status_code in [201, 422]

@pytest.mark.anyio
async def test_auth_null_password_attack(client: AsyncClient):
    """
    Attempt to send actual None/null as password (not string "None").
    """
    payload = {
        "email": "nullpass@example.com",
        "password": None,
        "role": "user",
        "fullname": "Test"
    }
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422

@pytest.mark.anyio
async def test_auth_prototype_pollution_fields(client: AsyncClient):
    """
    Attempt to pollute prototype using special keys.
    Python is generally immune, but good to check input sanitization.
    """
    payload = {
        "email": "proto@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "Test",
        "__proto__": {"isAdmin": True},
        "constructor": {"prototype": {"isAdmin": True}}
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    


    assert response.status_code in [201, 422]
    if response.status_code == 201:
        data = response.json()
        assert "__proto__" not in data

        assert data.get("is_superuser", False) is False

@pytest.mark.anyio
async def test_auth_email_parameter_pollution(client: AsyncClient):
    """
    Attempt to send email as a list (HPP - HTTP Parameter Pollution style in JSON).
    """
    payload = {
        "email": ["user@example.com", "admin@example.com"],
        "password": "Password12345!",
        "role": "user",
        "fullname": "Test"
    }
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422

@pytest.mark.anyio
async def test_auth_password_unicode_normalization(client: AsyncClient, create_user):
    """
    Test if password normalizes (e.g. half-width vs full-width chars).
    If it normalizes, 'Ａ' (full width) might match 'A' (standard).
    Usually hashing is strictly byte-based, so they should NOT match.
    """
    email = "unicode_pass@example.com"



    std_pass = "Password12345!A"
    
    await create_user(email, std_pass)
    

    full_width_pass = "Password12345!Ａ" 
    
    response = await client.post("/api/v1/auth/login", data={"username": email, "password": full_width_pass})
    


    assert response.status_code == 400
