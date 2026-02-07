from textwrap import dedent
from core.models import User
from mailing.send_email import send_email


async def send_email_confirmed(
    user: User,
):
    recipient = user.email
    subject = "Email confirmed"

    plain_content = dedent(
        f"""\
        Dear {recipient},
        Your email has been successfully confirmed.
        Welcome to the system!
        """
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #ffffff; margin: 0; padding: 40px 0;">
        <div style="max-width: 400px; margin: 0 auto; padding: 20px;">
            
            <h1 style="font-size: 28px; font-weight: 600; color: #28a745; margin: 0 0 16px 0; letter-spacing: -1px;">
                Email Confirmed
            </h1>
            
            <p style="font-size: 16px; color: #6e6e73; line-height: 1.5; margin-bottom: 32px;">
                Your email <span style="color: #000000; font-weight: 500;">{recipient}</span> has been successfully verified.
            </p>

            <div style="border-top: 1px solid #f2f2f7; padding-top: 24px;">
                 <p style="font-size: 14px; color: #86868b; margin: 0;">
                    You can now access all features of our service.
                </p>
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