import pytest
from httpx import AsyncClient



EXTREME_NAMES = [
    ("Кириллица", "Иван Иванов"),
    ("Китайский", "王明"),
    ("Арабский", "عبد الله"),
    ("Смешанный", "User123_тест_测试"),
    ("Zalgo", "Hęľłö Wóŕłď"),
    ("Emoji Only", "🦄🌈"),
    ("Whitespace", "   User   "),
    ("Tabs/Newlines", "User\tName\nHere"),
]

EXTREME_PASSWORDS = [
    "password with spaces",
    "pass\tword",
    "pass\nword",
    "€uroSign",
    "😊SmilingFace",
    "' OR '1'='1",
    "<script>alert(1)</script>",
]



WEIRD_EMAILS = [

    "disposable.style.email.with+symbol@example.com",
    "other.email-with-hyphen@example.com",
    "fully-qualified-domain@example.com",


    "example-indeed@strange-example.com",



]



@pytest.mark.anyio
@pytest.mark.parametrize("desc, name_value", EXTREME_NAMES)
async def test_register_extreme_usernames(client: AsyncClient, desc, name_value):
    """Test registration with various unicode scripts and whitespace."""
    payload = {
        "email": f"extreme_{desc.replace(' ', '_')}@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": name_value,
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    



    assert response.status_code in [201, 422], f"Failed on {desc}: {name_value}. Status: {response.status_code}"
    
    if response.status_code == 201:
        data = response.json()

        assert data["fullname"] == name_value


@pytest.mark.anyio
@pytest.mark.parametrize("password", EXTREME_PASSWORDS)
async def test_register_extreme_passwords(client: AsyncClient, password):
    """Test registration with complex passwords."""

    import hashlib
    email_hash = hashlib.md5(password.encode()).hexdigest()
    email = f"pass_{email_hash}@example.com"
    
    payload = {
        "email": email,
        "password": password,
        "role": "user",
        "fullname": "Test User",
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    


    assert response.status_code in [201, 422]
    
    if response.status_code == 201:

        login_resp = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
        assert login_resp.status_code in [200, 204], f"Could not login with password: {password}"


@pytest.mark.anyio
@pytest.mark.parametrize("email", WEIRD_EMAILS)
async def test_register_weird_emails(client: AsyncClient, email):
    """Test registration with valid but unusual emails."""
    payload = {
        "email": email,
        "password": "Password12345!",
        "role": "user",
        "fullname": "Test",
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    


    assert response.status_code in [201, 422], f"Crashed or unexpected error on email: {email}"


@pytest.mark.anyio
async def test_null_byte_attack(client: AsyncClient):
    """Test handling of null bytes in strings (common C-based vulnerability)."""



    payload = {
        "email": "nullbyte@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "User\u0000Name",
        "is_active": True,
        "is_verified": False
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    




    if response.status_code == 500:
        pytest.fail("Server crashed on NULL byte input!")
    
    assert response.status_code in [201, 400, 422]

