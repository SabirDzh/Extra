from textwrap import dedent
import secrets
from core.models import User
from mailing.send_email import send_email


async def send_password_reset_email(
    user: User,
    new_password: str,
):
    recipient = user.email
    subject = "Your New Password"

    plain_content = dedent(
        f"""\
        Hello,
        Your password has been reset. Your new temporary password is: {new_password}
        Please log in and change it as soon as possible.
        """
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 40px 0;">
        <div style="max-width: 400px; margin: 0 auto; padding: 20px;">

            <h1 style="font-size: 28px; font-weight: 600; color: #000000; margin: 0 0 16px 0; letter-spacing: -1px;">
                Password Reset
            </h1>

            <p style="font-size: 16px; color: #6e6e73; line-height: 1.5; margin-bottom: 32px;">
                Your password for account <span style="color: #000000; font-weight: 500;">{recipient}</span> has been reset.
            </p>

            <div style="background-color: #f2f2f7; padding: 20px; border-radius: 12px; margin-bottom: 32px; text-align: center;">
                <p style="font-size: 14px; color: #86868b; margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">
                    New Password
                </p>
                <code style="font-size: 24px; font-weight: 600; color: #000000; letter-spacing: 2px;">
                    {new_password}
                </code>
            </div>

            <p style="font-size: 14px; color: #86868b; line-height: 1.5; margin-bottom: 40px;">
                Please use this password to log in and change it in your profile settings.
            </p>

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
