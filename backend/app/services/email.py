"""Email delivery service for notifications and password recovery."""

from __future__ import annotations

import asyncio
from email.message import EmailMessage
import logging
import smtplib

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _build_reset_email_body(to_email: str, reset_link: str, expire_minutes: int, app_name: str) -> tuple[str, str]:
    """Return (plain_text, html) email body."""
    plain = f"""Hello,

We received a request to reset your password for {app_name}.

Click the link below to set a new password (valid for {expire_minutes} minutes):
{reset_link}

If you did not request this password reset, you can safely ignore this email. Your account remains secure.

Best regards,
The {app_name} Team
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Your Password</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #1e293b;
      background-color: #f8fafc;
      margin: 0;
      padding: 0;
    }}
    .container {{
      max-width: 540px;
      margin: 40px auto;
      background: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
      border: 1px solid #e2e8f0;
    }}
    .header {{
      padding: 28px 32px;
      background: #0f172a;
      color: #ffffff;
      text-align: center;
    }}
    .header h1 {{
      margin: 0;
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.02em;
    }}
    .content {{
      padding: 32px;
    }}
    .btn-container {{
      margin: 28px 0;
      text-align: center;
    }}
    .btn {{
      display: inline-block;
      padding: 12px 28px;
      background-color: #2563eb;
      color: #ffffff !important;
      text-decoration: none;
      font-weight: 500;
      font-size: 15px;
      border-radius: 8px;
    }}
    .footer {{
      padding: 20px 32px;
      background: #f1f5f9;
      font-size: 12px;
      color: #64748b;
      text-align: center;
      border-top: 1px solid #e2e8f0;
    }}
    .break-link {{
      word-break: break-all;
      color: #2563eb;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>{app_name}</h1>
    </div>
    <div class="content">
      <p>Hello,</p>
      <p>We received a request to reset your password for your account (<strong>{to_email}</strong>).</p>
      <div class="btn-container">
        <a href="{reset_link}" class="btn" target="_blank">Reset Password</a>
      </div>
      <p style="font-size: 13px; color: #64748b;">This link will expire in <strong>{expire_minutes} minutes</strong>. If you did not request a password change, please ignore this email.</p>
      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
      <p style="font-size: 12px; color: #64748b;">If the button doesn't work, copy and paste this link into your browser:</p>
      <p><a href="{reset_link}" class="break-link">{reset_link}</a></p>
    </div>
    <div class="footer">
      &copy; {app_name}. All rights reserved.
    </div>
  </div>
</body>
</html>
"""
    return plain, html


def _send_smtp_sync(
    *,
    to_email: str,
    subject: str,
    plain_content: str,
    html_content: str,
    settings: Settings,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    from_header = f"{settings.smtp_from_name} <{settings.smtp_from_email}>" if settings.smtp_from_name else settings.smtp_from_email
    msg["From"] = from_header
    msg["To"] = to_email

    msg.set_content(plain_content)
    msg.add_alternative(html_content, subtype="html")

    port = settings.smtp_port or (465 if settings.smtp_port == 465 else 587)
    if port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, port, timeout=15) as server:
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, port, timeout=15) as server:
            if settings.smtp_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)


async def send_password_reset_email(
    to_email: str,
    reset_link: str,
    settings: Settings | None = None,
) -> None:
    """Send a password reset email or log it if SMTP is unconfigured."""
    settings = settings or get_settings()
    plain, html = _build_reset_email_body(
        to_email=to_email,
        reset_link=reset_link,
        expire_minutes=settings.password_reset_token_expire_minutes,
        app_name=settings.app_name,
    )

    if not settings.smtp_host:
        logger.info(
            "\n" + "=" * 80 + "\n"
            "PASSWORD RESET LINK GENERATED (SMTP not configured, logging link):\n"
            "To: %s\n"
            "Reset Link: %s\n"
            "Valid for: %d minutes\n"
            + "=" * 80 + "\n",
            to_email,
            reset_link,
            settings.password_reset_token_expire_minutes,
        )
        return

    try:
        await asyncio.to_thread(
            _send_smtp_sync,
            to_email=to_email,
            subject=f"Reset your {settings.app_name} password",
            plain_content=plain,
            html_content=html,
            settings=settings,
        )
        logger.info("Password reset email sent to %s via SMTP", to_email)
    except Exception as exc:
        logger.exception("Failed to send password reset email via SMTP: %s", exc)
        # Log the link as fallback so users in dev or misconfigured SMTP don't get locked out
        logger.warning(
            "Fallback password reset link for %s: %s",
            to_email,
            reset_link,
        )
