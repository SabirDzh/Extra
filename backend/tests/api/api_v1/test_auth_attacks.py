import pytest
from httpx import AsyncClient

# --- ADVANCED ATTACK DATASETS ---

# 1. SQL Truncation / Whitespace Padding
# Attempt to register "admin" by using "admin          [x]"
# If DB truncates, it might overwrite or collide with "admin".
TRUNCATION_ATTEMPTS = [
    "admin" + " " * 255 + "x",
    "admin" + "\t" * 100,
]

# 2. Parameter Pollution / Duplicate Keys
# In JSON, duplicate keys usually result in the last one being used.
# We test this behavior implicitly (clients usually handle dicts, so raw payload needed for duplicate keys).
# But we can test array injection if backend expects string.

# 3. Format Strings (Python/C)
FORMAT_STRINGS = [
    "%s%s%s%s%s",
    "{0}{0}{0}",
    "{{7*7}}", # SSTI (Server Side Template Injection) probe
    "${7*7}",
]

# 4. Encoding / Homoglyphs
# "admin" using Cyrillic 'a' (U+0430) instead of Latin 'a' (U+0061)
HOMOGLYPH_EMAIL = "аdmin@example.com" 

# --- TESTS ---

@pytest.mark.anyio
@pytest.mark.parametrize("padding", TRUNCATION_ATTEMPTS)
async def test_auth_sql_truncation_attack(client: AsyncClient, padding):
    """
    Attempt to register a user with a very long email/name to cause DB truncation.
    If truncation happens silently, "admin...x" becomes "admin".
    """
    payload = {
        "email": f"truncate_{padding[:50]}@example.com", # Shorten email to pass basic format validation
        "password": "Password12345!",
        "role": "user",
        "fullname": padding # Inject padding into name
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # 422 (Too long) is good. 201 is also fine IF it saves the full string or handles it safely.
    # 500 is FAIL.
    assert response.status_code in [201, 422]
    
    if response.status_code == 201:
        # Verify it wasn't silently truncated to something dangerous if we intended that
        # (Though here we just check stability)
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
    
    # API should just save it as string (201) if no strict regex is enforced.
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
    # MUST be rejected (422)
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
    # 201 means system supports UTF-8 emails/IDN (good).
    # 422 means strict ASCII policy (also good security-wise).
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
    # Pydantic should catch type mismatch (expecting str, got NoneType)
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
    
    # Should ignore extra fields (201) or reject (422).
    # If 201, verify no pollution happened (logic check).
    assert response.status_code in [201, 422]
    if response.status_code == 201:
        data = response.json()
        assert "__proto__" not in data
        # Ensure normal user role
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
    # Should be 422 (Type mismatch)
    assert response.status_code == 422

@pytest.mark.anyio
async def test_auth_password_unicode_normalization(client: AsyncClient, create_user):
    """
    Test if password normalizes (e.g. half-width vs full-width chars).
    If it normalizes, 'Ａ' (full width) might match 'A' (standard).
    Usually hashing is strictly byte-based, so they should NOT match.
    """
    email = "unicode_pass@example.com"
    # Full-width 'Password12345!' (ｕｎｉｃｏｄｅ)
    # Let's use a simpler check: 'Ａ' vs 'A'
    # Register with standard 'Password12345!A'
    std_pass = "Password12345!A"
    
    await create_user(email, std_pass)
    
    # Try login with full-width 'Ａ' -> 'Password12345!Ａ'
    full_width_pass = "Password12345!Ａ" 
    
    response = await client.post("/api/v1/auth/login", data={"username": email, "password": full_width_pass})
    
    # Expect 400 (Bad credentials) because they are different bytes/chars.
    # If 200/204, then dangerous normalization is happening.
    assert response.status_code == 400
