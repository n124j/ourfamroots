"""Email sending service using Python stdlib smtplib (no extra deps).

Runs the blocking SMTP call in a thread via asyncio.to_thread so it
never blocks the event loop.
"""
from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from src.config import get_settings

log = structlog.get_logger(__name__)


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
    reply_to: str | None = None,
) -> None:
    """Send an email asynchronously. Silently logs errors rather than crashing."""
    settings = get_settings()

    def _send() -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = settings.email_from
        msg["To"]      = to
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_user and settings.smtp_password:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()  # required again after STARTTLS upgrade
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.email_from, to, msg.as_string())

    try:
        await asyncio.to_thread(_send)
        log.info("email.sent", to=to, subject=subject)
    except Exception as exc:
        log.error("email.failed", to=to, subject=subject, error=str(exc))


# ── Email templates ────────────────────────────────────────────────────────────

def account_created_email(display_name: str, activate_url: str, created_by: str) -> tuple[str, str]:
    """Email sent when an admin creates an account for a new user."""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#1e293b;margin:0 0 8px;">You've been added to OurFamRoots 🌳</h1>
    <p style="color:#64748b;margin:0 0 6px;">Hi {display_name},</p>
    <p style="color:#64748b;margin:0 0 24px;">
      <strong>{created_by}</strong> has created a OurFamRoots account for you.
      Click the button below to set your password and activate your account.
    </p>
    <a href="{activate_url}"
       style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">
      Set password &amp; activate account
    </a>
    <p style="color:#94a3b8;font-size:12px;margin:24px 0 0;">
      This link expires in 1 hour. If you weren't expecting this, you can safely ignore it.
    </p>
    <p style="color:#94a3b8;font-size:11px;margin:8px 0 0;word-break:break-all;">
      Or copy this URL: {activate_url}
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"Hi {display_name},\n\n"
        f"{created_by} has created a OurFamRoots account for you.\n\n"
        f"Set your password and activate your account by visiting:\n\n"
        f"{activate_url}\n\n"
        f"This link expires in 1 hour."
    )
    return html, text


def password_reset_email(display_name: str, reset_url: str) -> tuple[str, str]:
    """Returns (html_body, text_body) for the password-reset email."""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#1e293b;margin:0 0 8px;">Reset your password</h1>
    <p style="color:#64748b;margin:0 0 6px;">Hi {display_name},</p>
    <p style="color:#64748b;margin:0 0 24px;">
      We received a request to reset your OurFamRoots password.
      Click the button below to choose a new one.
    </p>
    <a href="{reset_url}"
       style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">
      Reset password
    </a>
    <p style="color:#94a3b8;font-size:12px;margin:24px 0 0;">
      This link expires in 1 hour. If you didn't request a reset, you can safely ignore this email.
    </p>
    <p style="color:#94a3b8;font-size:11px;margin:8px 0 0;word-break:break-all;">
      Or copy this URL: {reset_url}
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"Hi {display_name},\n\n"
        f"We received a request to reset your OurFamRoots password.\n\n"
        f"Reset your password by visiting:\n\n"
        f"{reset_url}\n\n"
        f"This link expires in 1 hour. If you didn't request a reset, ignore this email."
    )
    return html, text


def account_deactivated_email(display_name: str) -> tuple[str, str]:
    """Email sent when an admin deactivates a user's account."""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#1e293b;margin:0 0 8px;">Your account has been deactivated</h1>
    <p style="color:#64748b;margin:0 0 6px;">Hi {display_name},</p>
    <p style="color:#64748b;margin:0 0 24px;">
      An administrator has deactivated your OurFamRoots account.
      You will no longer be able to sign in. If you believe this is a mistake,
      please contact your administrator.
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"Hi {display_name},\n\n"
        f"An administrator has deactivated your OurFamRoots account.\n\n"
        f"You will no longer be able to sign in. If you believe this is a mistake, "
        f"please contact your administrator.\n"
    )
    return html, text


def account_verified_by_admin_email(display_name: str, login_url: str) -> tuple[str, str]:
    """Email sent when an admin manually verifies a user's account."""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#1e293b;margin:0 0 8px;">Your account is verified 🎉</h1>
    <p style="color:#64748b;margin:0 0 6px;">Hi {display_name},</p>
    <p style="color:#64748b;margin:0 0 24px;">
      An administrator has verified your OurFamRoots account.
      You can now sign in and start building your family tree.
    </p>
    <a href="{login_url}"
       style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">
      Sign in now
    </a>
  </div>
</body>
</html>
"""
    text = (
        f"Hi {display_name},\n\n"
        f"An administrator has verified your OurFamRoots account.\n\n"
        f"You can now sign in at:\n\n{login_url}\n"
    )
    return html, text


def account_unverified_by_admin_email(display_name: str) -> tuple[str, str]:
    """Email sent when an admin revokes a user's email verification."""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#1e293b;margin:0 0 8px;">Account verification removed</h1>
    <p style="color:#64748b;margin:0 0 6px;">Hi {display_name},</p>
    <p style="color:#64748b;margin:0 0 24px;">
      An administrator has removed the email verification from your OurFamRoots account.
      You will not be able to sign in until your account is verified again.
      Please contact your administrator if you believe this is a mistake.
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"Hi {display_name},\n\n"
        f"An administrator has removed the email verification from your OurFamRoots account.\n\n"
        f"You will not be able to sign in until your account is verified again.\n"
        f"Please contact your administrator if you believe this is a mistake.\n"
    )
    return html, text


def tree_invitation_email(
    invitee_email: str,
    inviter_name: str,
    tree_name: str,
    role: str,
    accept_url: str,
    message: str | None = None,
) -> tuple[str, str]:
    """Email sent when a user is invited to join a family tree."""
    role_label = {"VIEWER": "Viewer", "EDITOR": "Editor", "ADMIN": "Admin"}.get(role, role.capitalize())
    message_block = (
        f'<p style="color:#64748b;margin:0 0 16px;padding:12px 16px;'
        f'background:#f8fafc;border-left:3px solid #6366f1;border-radius:4px;">'
        f'"{message}"</p>'
    ) if message else ""
    message_text = f'\n"{message}"\n' if message else ""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#1e293b;margin:0 0 8px;">You've been invited to a family tree 🌳</h1>
    <p style="color:#64748b;margin:0 0 16px;">
      <strong>{inviter_name}</strong> has invited you to join
      <strong>{tree_name}</strong> as a <strong>{role_label}</strong>.
    </p>
    {message_block}
    <a href="{accept_url}"
       style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">
      Accept invitation
    </a>
    <p style="color:#94a3b8;font-size:12px;margin:24px 0 0;">
      This invitation expires in 7 days. If you weren't expecting this, you can safely ignore it.
    </p>
    <p style="color:#94a3b8;font-size:11px;margin:8px 0 0;word-break:break-all;">
      Or copy this URL: {accept_url}
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"You've been invited to a family tree!\n\n"
        f"{inviter_name} has invited you to join {tree_name} as a {role_label}.\n"
        f"{message_text}\n"
        f"Accept the invitation by visiting:\n\n{accept_url}\n\n"
        f"This invitation expires in 7 days. If you weren't expecting this, ignore this email."
    )
    return html, text


def verification_email(display_name: str, verify_url: str) -> tuple[str, str]:
    """Returns (html_body, text_body) for the email-verification email."""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#1e293b;margin:0 0 8px;">Welcome to OurFamRoots 🌳</h1>
    <p style="color:#64748b;margin:0 0 24px;">Hi {display_name}, please verify your email address to activate your account and start building your family tree.</p>
    <a href="{verify_url}"
       style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">
      Verify email address
    </a>
    <p style="color:#94a3b8;font-size:12px;margin:24px 0 0;">
      This link expires in 1 hour. If you didn't create an account, you can ignore this email.
    </p>
    <p style="color:#94a3b8;font-size:11px;margin:8px 0 0;word-break:break-all;">
      Or copy this URL: {verify_url}
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"Welcome to OurFamRoots!\n\n"
        f"Hi {display_name}, please verify your email address by visiting:\n\n"
        f"{verify_url}\n\n"
        f"This link expires in 1 hour."
    )
    return html, text


def account_deletion_request_email(display_name: str, confirm_url: str) -> tuple[str, str]:
    """Email sent when a user requests account deletion — contains confirmation link."""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#dc2626;margin:0 0 8px;">Confirm account deletion</h1>
    <p style="color:#64748b;margin:0 0 6px;">Hi {display_name},</p>
    <p style="color:#64748b;margin:0 0 16px;">
      We received a request to permanently delete your OurFamRoots account and all associated data.
    </p>
    <p style="color:#64748b;margin:0 0 24px;">
      Click the button below to confirm. <strong>This action cannot be undone.</strong>
    </p>
    <a href="{confirm_url}"
       style="display:inline-block;background:#dc2626;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">
      Confirm account deletion
    </a>
    <p style="color:#94a3b8;font-size:12px;margin:24px 0 0;">
      This link expires in 24 hours. If you did not request this, you can safely ignore this email — your account will not be deleted.
    </p>
    <p style="color:#94a3b8;font-size:11px;margin:8px 0 0;word-break:break-all;">
      Or copy this URL: {confirm_url}
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"Hi {display_name},\n\n"
        f"We received a request to permanently delete your OurFamRoots account.\n\n"
        f"Confirm the deletion by visiting:\n\n"
        f"{confirm_url}\n\n"
        f"This link expires in 24 hours. If you did not request this, ignore this email."
    )
    return html, text


def contact_form_email(
    sender_name: str,
    sender_email: str,
    sender_phone: str | None,
    subject: str,
    message: str,
) -> tuple[str, str]:
    """Notification email sent to the site owner when a visitor submits the contact form."""
    phone_row = (
        f'<tr><td style="padding:6px 0;color:#64748b;font-size:13px;width:110px">Phone</td>'
        f'<td style="padding:6px 0;color:#1e293b;font-size:13px">{sender_phone}</td></tr>'
    ) if sender_phone else ""
    phone_text = f"Phone:    {sender_phone}\n" if sender_phone else ""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:540px;margin:0 auto;background:#fff;border-radius:12px;
              padding:32px;border:1px solid #e2e8f0;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px;">
      <span style="font-size:28px">&#127795;</span>
      <div>
        <div style="font-size:11px;font-weight:700;color:#6366f1;letter-spacing:1px;
                    text-transform:uppercase;">OurFamRoots</div>
        <div style="font-size:18px;font-weight:700;color:#1e293b;">New Contact Form Submission</div>
      </div>
    </div>

    <div style="background:#f8fafc;border-radius:8px;padding:16px 20px;margin-bottom:24px;">
      <table style="border-collapse:collapse;width:100%">
        <tr>
          <td style="padding:6px 0;color:#64748b;font-size:13px;width:110px">From</td>
          <td style="padding:6px 0;color:#1e293b;font-size:13px;font-weight:600">{sender_name}</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#64748b;font-size:13px">Email</td>
          <td style="padding:6px 0;font-size:13px">
            <a href="mailto:{sender_email}" style="color:#6366f1">{sender_email}</a>
          </td>
        </tr>
        {phone_row}
        <tr>
          <td style="padding:6px 0;color:#64748b;font-size:13px">Subject</td>
          <td style="padding:6px 0;color:#1e293b;font-size:13px">{subject}</td>
        </tr>
      </table>
    </div>

    <div>
      <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;
                  letter-spacing:1px;margin-bottom:10px;">Message</div>
      <div style="color:#1e293b;font-size:14px;line-height:1.7;white-space:pre-wrap;">{message}</div>
    </div>

    <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">
    <p style="color:#94a3b8;font-size:11px;margin:0;">
      Sent via the OurFamRoots contact form &#183;
      Reply directly to this email to respond to {sender_name}.
    </p>
  </div>
</body>
</html>"""

    text = (
        f"New OurFamRoots contact form submission\n"
        f"{'=' * 40}\n\n"
        f"From:     {sender_name}\n"
        f"Email:    {sender_email}\n"
        f"{phone_text}"
        f"Subject:  {subject}\n\n"
        f"Message:\n{message}\n\n"
        f"{'=' * 40}\n"
        f"Reply to this email to respond to {sender_name}."
    )
    return html, text


def login_verification_email(display_name: str, verify_url: str, ip_address: str | None) -> tuple[str, str]:
    """Email sent when a login attempt is made on an account with active sessions."""
    ip_info = f" from IP address <strong>{ip_address}</strong>" if ip_address else ""
    ip_text = f" from IP address {ip_address}" if ip_address else ""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#d97706;margin:0 0 8px;">New login attempt detected</h1>
    <p style="color:#64748b;margin:0 0 6px;">Hi {display_name},</p>
    <p style="color:#64748b;margin:0 0 16px;">
      Someone is trying to sign in to your OurFamRoots account{ip_info}.
      Your account is currently signed in on another device.
    </p>
    <p style="color:#64748b;margin:0 0 24px;">
      If this is you, click the button below to verify this login. Your other sessions will be signed out.
    </p>
    <a href="{verify_url}"
       style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">
      Verify and sign in
    </a>
    <p style="color:#94a3b8;font-size:12px;margin:24px 0 0;">
      This link expires in 1 hour. If you didn't attempt to sign in, you can safely ignore this email
      &mdash; your account remains secure.
    </p>
    <p style="color:#94a3b8;font-size:11px;margin:8px 0 0;word-break:break-all;">
      Or copy this URL: {verify_url}
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"Hi {display_name},\n\n"
        f"Someone is trying to sign in to your OurFamRoots account{ip_text}.\n"
        f"Your account is currently signed in on another device.\n\n"
        f"If this is you, verify this login by visiting:\n\n"
        f"{verify_url}\n\n"
        f"This link expires in 1 hour. If you didn't attempt to sign in, ignore this email."
    )
    return html, text


def session_takeover_email(display_name: str, old_ip: str | None, change_password_url: str) -> tuple[str, str]:
    """Email sent after a verified login signs out a previous session."""
    ip_info = f" (IP: <strong>{old_ip}</strong>)" if old_ip else ""
    ip_text = f" (IP: {old_ip})" if old_ip else ""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#dc2626;margin:0 0 8px;">Security alert</h1>
    <p style="color:#64748b;margin:0 0 6px;">Hi {display_name},</p>
    <p style="color:#64748b;margin:0 0 16px;">
      A new login to your OurFamRoots account was verified. Your previous session{ip_info} has been signed out.
    </p>
    <p style="color:#64748b;margin:0 0 24px;">
      For your security, we strongly recommend changing your password immediately.
    </p>
    <a href="{change_password_url}"
       style="display:inline-block;background:#dc2626;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">
      Change your password
    </a>
    <p style="color:#94a3b8;font-size:12px;margin:24px 0 0;">
      If you did not initiate this login, your account may be compromised.
      Change your password immediately and contact support.
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"Hi {display_name},\n\n"
        f"A new login to your OurFamRoots account was verified. "
        f"Your previous session{ip_text} has been signed out.\n\n"
        f"For your security, we strongly recommend changing your password immediately.\n\n"
        f"Change your password at:\n{change_password_url}\n\n"
        f"If you did not initiate this login, your account may be compromised. "
        f"Change your password immediately and contact support."
    )
    return html, text


def broadcast_email(
    subject: str,
    body: str,
    recipient_name: str,
    category: str = "notice",
    unsubscribe_url: str = "",
) -> tuple[str, str]:
    """Email template for Super Admin broadcast messages."""
    category_labels = {
        "notice":  ("Notice",       "#6366f1"),
        "alert":   ("Alert",        "#dc2626"),
        "event":   ("Event",        "#059669"),
        "update":  ("Update",       "#d97706"),
    }
    label, color = category_labels.get(category, ("Notice", "#6366f1"))

    body_html = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

    unsub_html = ""
    unsub_text = ""
    if unsubscribe_url:
        unsub_html = (
            f'<p style="color:#94a3b8;font-size:11px;margin:8px 0 0;">'
            f'Don\'t want to receive these emails? '
            f'<a href="{unsubscribe_url}" style="color:#6366f1;text-decoration:underline;">Unsubscribe</a>'
            f'</p>'
        )
        unsub_text = f"\n\nTo unsubscribe from broadcast emails, visit: {unsubscribe_url}"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:540px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <div style="margin-bottom:20px;">
      <span style="display:inline-block;background:{color};color:#fff;font-size:11px;font-weight:700;
                   padding:3px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:0.5px;">
        {label}
      </span>
    </div>
    <h1 style="font-size:22px;font-weight:700;color:#1e293b;margin:0 0 8px;">{subject}</h1>
    <p style="color:#64748b;margin:0 0 20px;">Hi {recipient_name},</p>
    <div style="color:#334155;line-height:1.7;margin:0 0 24px;">
      {body_html}
    </div>
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0;">
    <p style="color:#94a3b8;font-size:12px;margin:0;">
      This message was sent by the OurFamRoots administrator. You are receiving this
      because you have an account on OurFamRoots.
    </p>
    {unsub_html}
  </div>
</body>
</html>
"""
    text = (
        f"[{label}] {subject}\n\n"
        f"Hi {recipient_name},\n\n"
        f"{body}\n\n"
        f"---\n"
        f"This message was sent by the OurFamRoots administrator."
        f"{unsub_text}"
    )
    return html, text


def change_request_submitted_email(
    owner_name: str,
    requester_name: str,
    tree_name: str,
    review_url: str,
    message: str | None = None,
) -> tuple[str, str]:
    """Email sent to a tree owner when someone Posts a proposed change for review."""
    message_block = (
        f'<p style="color:#64748b;margin:0 0 16px;padding:12px 16px;'
        f'background:#f8fafc;border-left:3px solid #6366f1;border-radius:4px;">'
        f'"{message}"</p>'
    ) if message else ""
    message_text = f'\n"{message}"\n' if message else ""
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <h1 style="font-size:22px;font-weight:700;color:#1e293b;margin:0 0 8px;">New proposed changes to review</h1>
    <p style="color:#64748b;margin:0 0 16px;">
      Hi {owner_name}, <strong>{requester_name}</strong> has proposed changes to
      <strong>{tree_name}</strong> and is waiting for your review.
    </p>
    {message_block}
    <a href="{review_url}"
       style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">
      Review changes
    </a>
    <p style="color:#94a3b8;font-size:11px;margin:24px 0 0;word-break:break-all;">
      Or copy this URL: {review_url}
    </p>
  </div>
</body>
</html>
"""
    text = (
        f"New proposed changes to review\n\n"
        f"Hi {owner_name}, {requester_name} has proposed changes to {tree_name} "
        f"and is waiting for your review.\n"
        f"{message_text}\n"
        f"Review the changes here:\n\n{review_url}"
    )
    return html, text


def change_request_resolved_email(
    requester_name: str,
    tree_name: str,
    approved: bool,
    decision_note: str | None = None,
    tree_url: str | None = None,
) -> tuple[str, str]:
    """Email sent to the requester once the tree owner approves or denies their proposal."""
    label, color = ("Approved", "#059669") if approved else ("Denied", "#dc2626")
    headline = (
        f"Your proposed changes to {tree_name} were approved"
        if approved
        else f"Your proposed changes to {tree_name} were denied"
    )
    note_block = (
        f'<p style="color:#64748b;margin:0 0 16px;padding:12px 16px;'
        f'background:#f8fafc;border-left:3px solid {color};border-radius:4px;">'
        f'"{decision_note}"</p>'
    ) if decision_note else ""
    note_text = f'\n"{decision_note}"\n' if decision_note else ""
    cta_html = (
        f'<a href="{tree_url}" style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;'
        f'padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;">View tree</a>'
        if approved and tree_url else ""
    )
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #e2e8f0;">
    <div style="margin-bottom:20px;">
      <span style="display:inline-block;background:{color};color:#fff;font-size:11px;font-weight:700;
                   padding:3px 10px;border-radius:20px;text-transform:uppercase;letter-spacing:0.5px;">
        {label}
      </span>
    </div>
    <h1 style="font-size:20px;font-weight:700;color:#1e293b;margin:0 0 8px;">{headline}</h1>
    <p style="color:#64748b;margin:0 0 16px;">Hi {requester_name},</p>
    {note_block}
    {cta_html}
  </div>
</body>
</html>
"""
    text = (
        f"[{label}] {headline}\n\n"
        f"Hi {requester_name},"
        f"{note_text}"
        f"{'' if not (approved and tree_url) else chr(10) + 'View the tree: ' + tree_url}"
    )
    return html, text
