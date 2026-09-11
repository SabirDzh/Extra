"""Unit tests for operational safety guards added during the project review."""

import uuid
from datetime import datetime, timezone

import pytest
from api.api_v1 import backups as backups_api
from api.api_v1 import certificates as certificates_api
from api.api_v1.product import _get_client_identifier
from core import certificate_pdf
from core.models.certificates import Certificate
from core.models.course import Course
from fastapi import HTTPException
from middlewares.requests_count_middleware import RequestsCountMiddlewareDispatch
from playwright.async_api import Error as PlaywrightError
from Services.product_analytics import track_product_view
from starlette.requests import Request
from starlette.responses import Response


class FakePage:
    """Minimal Playwright page double used without launching Chromium."""

    async def set_content(
        self,
        html_content: str,
        *,
        wait_until: str,
        timeout: int,
    ) -> None:
        assert "Certificate" in html_content
        assert wait_until == "networkidle"
        assert timeout > 0

    async def pdf(self, **kwargs: object) -> bytes:
        assert kwargs["format"] == "A4"
        return b"%PDF-test"


class FakeBrowser:
    """Minimal browser double that records resource cleanup."""

    def __init__(self) -> None:
        self.closed = False

    async def new_page(self, **kwargs: object) -> FakePage:
        assert kwargs["viewport"] == {"width": 1200, "height": 1600}
        return FakePage()

    async def close(self) -> None:
        self.closed = True


class FakeChromium:
    """Minimal Chromium launcher double."""

    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser

    async def launch(self, *, headless: bool) -> FakeBrowser:
        assert headless is True
        return self.browser


class FakePlaywright:
    """Playwright object exposing the Chromium launcher used by the service."""

    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = FakeChromium(browser)


class FakePlaywrightContext:
    """Async context manager returned by the patched Playwright factory."""

    def __init__(self, browser: FakeBrowser) -> None:
        self.playwright = FakePlaywright(browser)

    async def __aenter__(self) -> FakePlaywright:
        return self.playwright

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None


@pytest.mark.anyio
async def test_certificate_pdf_closes_browser_and_returns_pdf(monkeypatch) -> None:
    browser = FakeBrowser()
    monkeypatch.setattr(
        certificate_pdf,
        "async_playwright",
        lambda: FakePlaywrightContext(browser),
    )

    pdf_bytes = await certificate_pdf.async_generate_certificate_pdf(
        full_name="Certificate User",
        course_title="Certificate Course",
        certificate_number="CERT-1",
        issued_at=datetime.now(timezone.utc),
    )

    assert pdf_bytes == b"%PDF-test"
    assert browser.closed is True


@pytest.mark.anyio
async def test_certificate_download_returns_503_when_browser_is_unavailable(
    client,
    session,
    create_user,
    monkeypatch,
) -> None:
    user = await create_user("certificate-unavailable@test.com")
    course = Course(title="Certificate course", created_by=user.id, is_published=True)
    session.add(course)
    await session.flush()
    certificate = Certificate(user_id=user.id, course_id=course.id)
    session.add(certificate)
    await session.commit()
    await session.refresh(certificate)

    async def raise_browser_error(**kwargs: object) -> bytes:
        raise PlaywrightError("Chromium is unavailable")

    monkeypatch.setattr(
        certificates_api,
        "async_generate_certificate_pdf",
        raise_browser_error,
    )
    await client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "Password12345!"},
    )

    response = await client.get(
        f"/api/v1/certificates/{certificate.certificate_number}/download",
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Certificate generation is temporarily unavailable"


def test_backup_path_rejects_traversal(monkeypatch, tmp_path) -> None:
    archive = tmp_path / "backup_manual_20260827_120000.tar.gz"
    archive.write_bytes(b"backup")
    secret_file = tmp_path.parent / "secret.txt"
    secret_file.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(backups_api, "BACKUPS_DIR", tmp_path)

    assert backups_api._get_backup_path(archive.name) == archive.resolve()
    with pytest.raises(HTTPException) as error:
        backups_api._get_backup_path("../secret.txt")

    assert error.value.status_code == 404


class FakeRedis:
    """Small Redis double that records analytics retention updates."""

    def __init__(self) -> None:
        self.expirations: list[tuple[str, int]] = []

    async def pfadd(self, key: str, identifier: str) -> int:
        return 1

    async def zincrby(self, key: str, amount: int, member: str) -> None:
        return None

    async def expire(self, key: str, seconds: int) -> None:
        self.expirations.append((key, seconds))


@pytest.mark.anyio
async def test_product_analytics_sets_retention() -> None:
    redis = FakeRedis()

    await track_product_view(redis, uuid.uuid4(), "127.0.0.1")

    assert len(redis.expirations) == 2
    assert all(seconds > 0 for _, seconds in redis.expirations)


def test_product_analytics_does_not_trust_forwarded_for() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/products/test",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", b"203.0.113.1")],
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
        }
    )

    assert _get_client_identifier(request) == "127.0.0.1"


@pytest.mark.anyio
async def test_request_counter_bounds_unknown_paths() -> None:
    counter = RequestsCountMiddlewareDispatch(max_paths=2)

    async def call_next(request: Request) -> Response:
        return Response(status_code=200)

    for index in range(10):
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "scheme": "http",
                "path": f"/unknown/{index}",
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 12345),
                "server": ("test", 80),
            }
        )
        await counter(request, call_next)

    assert len(counter.counts) == 3
    assert counter.counts["__other__"].count == 8
