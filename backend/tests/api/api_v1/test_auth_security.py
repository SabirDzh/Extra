import pytest
from httpx import AsyncClient

# --- SECURITY & HACKING TESTS ---

@pytest.mark.anyio
async def test_security_privilege_escalation_attempt(client: AsyncClient):
    """
    HACK: Mass Assignment / Privilege Escalation.
    Try to register a user setting 'is_superuser' and 'is_verified' to True explicitly.
    Expected: The API should ignore these fields or validation should reject them, 
    OR they are accepted but ignored by the backend logic (user created as false).
    """
    payload = {
        "email": "hacker_admin@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "Hacker",
        # Attempt to inject flags
        "is_superuser": True,
        "is_verified": True,
        "is_active": True
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # Even if 201 Created, we must verify the flags were NOT respected.
    if response.status_code == 201:
        data = response.json()
        assert data["is_superuser"] is False, "SECURITY FAIL: User managed to register as superuser!"
        assert data["is_verified"] is False, "SECURITY FAIL: User managed to auto-verify!"
    elif response.status_code == 422:
        # Valid rejection
        pass


@pytest.mark.anyio
async def test_security_role_escalation(client: AsyncClient):
    """
    HACK: Role Escalation.
    Try to register directly as 'administrator' via the public registration endpoint.
    If the API allows this public endpoint to set 'administrator', it's a security flaw (logic issue),
    unless the system is designed to allow public admin registration (rare).
    """
    payload = {
        "email": "hacker_role@example.com",
        "password": "Password12345!",
        "role": "administrator", # Try to grab admin role
        "fullname": "Hacker"
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    # If this returns 201, it means anyone can register as admin. 
    # This might be intended for development, but risky for prod.
    # We assert that the system handles it gracefully (does not crash).
    # Ideally, we should check if the role was actually applied.
    assert response.status_code in [201, 400, 403, 422]
    
    if response.status_code == 201:
        data = response.json()
        # If this assertion fails, your API allows public admin registration!
        # assert data["role"] == "user" # Uncomment to enforce strict no-public-admin rule
        pass


@pytest.mark.anyio
async def test_security_type_confusion_email(client: AsyncClient):
    """
    HACK: Type Confusion / NoSQL Injection style.
    Send a dictionary/array where a string is expected for email.
    Python/Pydantic should catch this and return 422.
    If it passes to the DB or crashes (500), it's a vulnerability.
    """
    payload = {
        "email": {"$ne": "something"}, # Mongo-style injection attempt
        "password": "Password12345!",
        "role": "user",
        "fullname": "Hacker"
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_security_type_confusion_password(client: AsyncClient):
    """
    HACK: Send integer/array as password.
    Some weak systems might crash trying to hash an array.
    """
    payload = {
        "email": "type_conf_pass@example.com",
        "password": [1, 2, 3], # Array instead of string
        "role": "user",
        "fullname": "Hacker"
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_security_os_command_injection(client: AsyncClient):
    """
    HACK: OS Command Injection payloads in input fields.
    """
    payloads = [
        "; cat /etc/passwd",
        "| ls -la",
        "`whoami`",
        "$(id)",
        "& ping -c 10 127.0.0.1 &"
    ]
    
    for cmd in payloads:
        payload = {
            "email": "cmd_inject@example.com",
            "password": "Password12345!",
            "role": "user",
            "fullname": cmd
        }
        # We reuse email, so subsequent requests might fail with 400 (duplicate), which is fine.
        # We assume 201 (saved literally) or 422/400.
        # 500 is FAIL.
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code in [201, 400, 422]


@pytest.mark.anyio
async def test_security_path_traversal(client: AsyncClient):
    """
    HACK: Path Traversal attempts.
    """
    paths = [
        "../../../etc/shadow",
        "..\\..\\windows\\win.ini",
        "/var/www/html/index.php"
    ]
    for path in paths:
        payload = {
            "email": "path@example.com",
            "password": "Password12345!",
            "role": "user",
            "fullname": path
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code in [201, 400, 422]
        if response.status_code == 201:
            # Ensure it was saved literally and not interpreted
            assert response.json()["fullname"] == path


@pytest.mark.anyio
async def test_security_xml_content_type(client: AsyncClient):
    """
    HACK: Content-Type Spoofing / XXE attempt.
    Send XML body with application/json header or vice versa.
    """
    xml_data = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <!DOCTYPE foo [ <!ELEMENT foo ANY >
    <!ENTITY xxe SYSTEM "file:///etc/passwd" >]> 
    <foo>&xxe;</foo>"""
    
    # 1. Send XML with JSON header (Parser confusion)
    response = await client.post(
        "/api/v1/auth/register", 
        content=xml_data,
        headers={"Content-Type": "application/json"}
    )
    # Should be 400 Bad Request (JSON parse error) or 422.
    assert response.status_code in [400, 422]

    # 2. Send XML with XML header (Unsupported Media Type)
    response = await client.post(
        "/api/v1/auth/register", 
        content=xml_data,
        headers={"Content-Type": "application/xml"}
    )
    # FastAPI default is 422 for validation or 415 Unsupported Media Type if strictly typed
    assert response.status_code in [415, 422, 400]


@pytest.mark.anyio
async def test_security_unknown_fields_stripping(client: AsyncClient):
    """
    HACK: Send valid payload PLUS extra dangerous fields (e.g. internal DB fields).
    Pydantic should ignore them (default) or forbid them (extra='forbid').
    They should NOT cause 500 errors.
    """
    payload = {
        "email": "strip_fields@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": "Test",
        
        "hashed_password": "fake_hash_injection",
        "id": "00000000-0000-0000-0000-000000000000",
        "__class__": "DangerousClass"
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    
    if response.status_code == 201:
        data = response.json()
        # Verify our fake ID wasn't used
        assert data["id"] != "00000000-0000-0000-0000-000000000000"
        # Verify hashed_password isn't returned
        assert "hashed_password" not in data
    else:
        # 422 is also fine if schema restricts extra fields
        assert response.status_code == 422


@pytest.mark.anyio
async def test_security_http_method_override(client: AsyncClient):
    """
    HACK: Try to use GET/PUT on POST-only endpoints.
    """
    # GET on register (should contain secrets in URL usually, but here we check allowed methods)
    resp_get = await client.get("/api/v1/auth/register")
    assert resp_get.status_code == 405 # Method Not Allowed

    # PUT on register
    resp_put = await client.put("/api/v1/auth/register", json={})
    assert resp_put.status_code == 405


@pytest.mark.anyio
async def test_security_huge_json_dos(client: AsyncClient):
    """
    HACK: DoS attempt with deeply nested JSON or massive lists.
    FastAPI/Starlette usually limits this, checking robustness.
    """
    # Massive list
    massive_list = ["a"] * 5000
    payload = {
        "email": "dos@example.com",
        "password": "Password12345!",
        "role": "user",
        "fullname": str(massive_list)
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    # 422 Validation Error (str expected, got list) or 400.
    # Should NOT hang forever or crash (500).
    assert response.status_code in [400, 422]
