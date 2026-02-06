import pytest
from httpx import AsyncClient

# --- DATASETS ---

EXTREME_NAMES = [
    ("Кириллица", "Иван Иванов"),
    ("Китайский", "王明"),
    ("Арабский", "عبد الله"),
    ("Смешанный", "User123_тест_测试"),
    ("Zalgo", "Hęľłö Wóŕłď"),  # Simplified Zalgo-like
    ("Emoji Only", "🦄🌈"),
    ("Whitespace", "   User   "), # Should usually be trimmed or preserved
    ("Tabs/Newlines", "User\tName\nHere"),
]

EXTREME_PASSWORDS = [
    "password with spaces",
    "pass\tword",
    "pass\nword",
    "€uroSign",
    "😊SmilingFace",
    "' OR '1'='1", # SQL injection attempt in password
    "<script>alert(1)</script>", # XSS attempt in password
]

# RFC 5322 allows some very weird emails. 
# We test if the system handles them (either accepts or validation-rejects gracefully).
WEIRD_EMAILS = [
    # "very.common@example.com", # Standard
    "disposable.style.email.with+symbol@example.com",
    "other.email-with-hyphen@example.com",
    "fully-qualified-domain@example.com",
    # "user.name+tag+sorting@example.com",
    # "x@example.com", # 1 letter local part
    "example-indeed@strange-example.com",
    # "admin@mailserver1", # local domain, usually rejected by validators requiring TLD
    # "example@s.example", # 1 letter TLD? valid?
    # '"very.(),:;<>[]\".VERY.\"very@\\ \"very\".unusual"@strange.example.com', # Valid RFC, often rejected by simple regex
]

# --- TESTS ---

@pytest.mark.anyio
@pytest.mark.parametrize("desc, name_value", EXTREME_NAMES)
async def test_register_extreme_usernames(client: AsyncClient, desc, name_value):
    """Test registration with various unicode scripts and whitespace."""
    payload = {
        "email": f"extreme_{desc.replace(' ', '_')}@example.com",
        "password": "password12345",
        "role": "user",
        "username": {"first_name": name_value},
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # 201 Created is expected for Unicode.
    # 422 is expected if specific rules forbid chars (like tabs/newlines).
    # 500 is FAIL.
    assert response.status_code in [201, 422], f"Failed on {desc}: {name_value}. Status: {response.status_code}"
    
    if response.status_code == 201:
        data = response.json()
        # Verify encoding is preserved (round-trip)
        assert data["username"]["first_name"] == name_value


@pytest.mark.anyio
@pytest.mark.parametrize("password", EXTREME_PASSWORDS)
async def test_register_extreme_passwords(client: AsyncClient, password):
    """Test registration with complex passwords."""
    # Use a unique email for each password case to avoid collision
    import hashlib
    email_hash = hashlib.md5(password.encode()).hexdigest()
    email = f"pass_{email_hash}@example.com"
    
    payload = {
        "email": email,
        "password": password,
        "role": "user",
        "username": {"first_name": "Test User"},
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # Passwords should generally be accepted hashed.
    # Some validators might reject whitespace.
    assert response.status_code in [201, 422]
    
    if response.status_code == 201:
        # Verify we can login with this extreme password
        login_resp = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
        assert login_resp.status_code in [200, 204], f"Could not login with password: {password}"


@pytest.mark.anyio
@pytest.mark.parametrize("email", WEIRD_EMAILS)
async def test_register_weird_emails(client: AsyncClient, email):
    """Test registration with valid but unusual emails."""
    payload = {
        "email": email,
        "password": "password12345",
        "role": "user",
        "username": {"first_name": "Test"},
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # We mainly check it doesn't crash (500).
    # 201 or 422 are both "valid" system responses depending on strictness.
    assert response.status_code in [201, 422], f"Crashed or unexpected error on email: {email}"


@pytest.mark.anyio
async def test_null_byte_attack(client: AsyncClient):
    """Test handling of null bytes in strings (common C-based vulnerability)."""
    # Python/Postgres usually handle this, but it's a good stress test.
    # Null bytes in JSON strings are technically valid JSON escaped as \u0000, 
    # but many backends reject them because text fields in DBs (like Postgres) don't support null bytes.
    payload = {
        "email": "nullbyte@example.com",
        "password": "password12345",
        "role": "user",
        "username": {"first_name": "User\u0000Name"},
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # Should likely fail with 422 (Pydantic validation) or 400/500 (DB error).
    # Ideally 422 or 400. 500 implies unhandled DB exception.
    # Pydantic v2 might allow it, but Postgres/SQLite might crash or reject.
    # We want to ensure it's handled.
    if response.status_code == 500:
        pytest.fail("Server crashed on NULL byte input!")
    
    assert response.status_code in [201, 400, 422]
