"""Email delivery — sends the HTML newsletter via SMTP."""
from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.logger import get_logger

logger = get_logger("delivery.email")


@dataclass
class Recipient:
    email: str
    name: str = ""


def send_newsletter(
    html: str,
    recipients: list[dict],
    subject: str | None = None,
) -> None:
    """Send the newsletter HTML to all recipients via SMTP.

    Required environment variables:
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

    Optional:
        EMAIL_FROM_NAME  (default: "Tech Radar Agent")
    """
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    from_name = os.environ.get("EMAIL_FROM_NAME", "Tech Radar Agent")

    if subject is None:
        week = datetime.now().strftime("Week of %B %d, %Y")
        subject = f"🔭 Weekly Tech Radar — {week}"

    from_addr = f"{from_name} <{smtp_user}>"

    errors: list[str] = []

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)

        for user in recipients:
            to_email = user["email"]
            to_name = user.get("name", "")
            to_addr = f"{to_name} <{to_email}>" if to_name else to_email

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to_addr

            # Plain-text fallback
            plain = (
                "This newsletter requires an HTML-capable email client.\n"
                f"View it at: {to_email}"
            )
            msg.attach(MIMEText(plain, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))

            try:
                server.sendmail(smtp_user, [to_email], msg.as_string())
                logger.info("Email sent → %s", to_addr)
            except Exception as exc:
                logger.error("Failed to send to %s: %s", to_addr, exc)
                errors.append(f"{to_addr}: {exc}")

    if errors:
        raise RuntimeError(f"Delivery errors:\n" + "\n".join(errors))

    logger.info("All emails delivered successfully.")
