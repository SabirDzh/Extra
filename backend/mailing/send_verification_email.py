from textwrap import dedent
from urllib.parse import urlsplit, urlunsplit
from core.models import User
from core.config import settings
from mailing.send_email import send_email


def _force_https(url: str) -> str:
    if not url:
        return url
    parts = urlsplit(url)
    if not parts.scheme:
        return url
    return urlunsplit(("https", parts.netloc, parts.path, parts.query, parts.fragment))


async def send_verification_email(
    user: User,
    verification_link: str,
):
    recipient = user.email
    subject = "Verify your identity"

    confirm_url = verification_link or f"{settings.run.base_url}/confirm/{recipient}"
    confirm_url = _force_https(confirm_url)

    plain_content = dedent(
        f"""\
        To complete your registration for {recipient}, please verify your account.
        Follow this link: {confirm_url}
        """
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 40px 0;">
        <div style="max-width: 400px; margin: 0 auto; padding: 20px;">

            <h1 style="font-size: 28px; font-weight: 600; color: #000000; margin: 0 0 16px 0; letter-spacing: -1px;">
                Verify your identity
            </h1>

            <p style="font-size: 16px; color: #6e6e73; line-height: 1.5; margin-bottom: 32px;">
                To complete your registration for <span style="color: #000000; font-weight: 500;">{recipient}</span>, please verify your account.
            </p>

            <div style="margin-bottom: 40px;">
                <a href="{confirm_url}" style="background-color: #000000; color: #ffffff; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-size: 16px; font-weight: 500; display: inline-block;">
                    Verify Account
                </a>
            </div>

            <p style="font-size: 12px; color: #c1c1c6; margin-top: 60px; text-transform: uppercase; letter-spacing: 1px;">
                Secure Authentication Service
            </p>
        </div>
    </body>
    </html>
    """

    await send_email(
        recipient=recipient,
        subject=subject,
        plain_content=plain_content,
        html_content=html_content,
    )
