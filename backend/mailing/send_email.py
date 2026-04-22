import json
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)


async def send_email(
    recipient: str,
    subject: str,
    plain_content: str,
    html_content: str = "",
):
    message = MIMEMultipart("alternative")
    message["From"] = f"{config['SENDER_NAME']} <{config['SENDER_EMAIL']}>"
    message["To"] = recipient
    message["Subject"] = subject

    message.attach(MIMEText(plain_content, "plain", "utf-8"))

    if html_content:
        message.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            message,
            hostname=config["SMTP_SERVER"],
            port=config["SMTP_PORT"],
            username=config["SENDER_EMAIL"],
            password=config["SENDER_PASSWORD"],
            start_tls=True,
        )
        print(f"Success: Email delivered to {recipient}")
    except Exception as e:
        print(f"Error: Delivery failed to {recipient}. Reason: {e}")