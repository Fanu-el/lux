import asyncio
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email import Email, EmailStatus

logger = logging.getLogger(__name__)


async def send_email(
    db: Session,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    email_log = Email(
        to_email=to_email,
        subject=subject,
        body=body,
        status=EmailStatus.SENT,
    )

    try:
        if settings.mail_provider == "resend":
            await _send_with_resend(to_email=to_email, subject=subject, body=body)
        else:
            await _send_with_fastapi_mail(to_email=to_email, subject=subject, body=body)
    except Exception as exc:
        logger.error(
            "Failed to send email to %s via %s: %s",
            to_email,
            settings.mail_provider,
            exc,
        )
        email_log.status = EmailStatus.FAILED
        email_log.error_message = str(exc)
        db.add(email_log)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email",
        ) from exc

    db.add(email_log)
    db.commit()


async def _send_with_resend(to_email: str, subject: str, body: str) -> None:
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")
    if not settings.mail_from:
        raise RuntimeError("MAIL_FROM is not configured")

    import resend

    resend.api_key = settings.resend_api_key
    from_address = (
        f"{settings.mail_from_name} <{settings.mail_from}>"
        if settings.mail_from_name
        else settings.mail_from
    )
    params: resend.Emails.SendParams = {
        "from": from_address,
        "to": [to_email],
        "subject": subject,
        "html": body,
    }
    await asyncio.to_thread(resend.Emails.send, params)


async def _send_with_fastapi_mail(to_email: str, subject: str, body: str) -> None:
    if (
        not settings.mail_username
        or not settings.mail_password
        or not settings.mail_from
    ):
        raise RuntimeError("Email settings are incomplete")

    from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

    config = ConnectionConfig(
        MAIL_USERNAME=settings.mail_username,
        MAIL_PASSWORD=settings.mail_password,
        MAIL_FROM=settings.mail_from,
        MAIL_FROM_NAME=settings.mail_from_name,
        MAIL_SERVER=settings.mail_server,
        MAIL_PORT=settings.mail_port,
        MAIL_STARTTLS=settings.mail_starttls,
        MAIL_SSL_TLS=settings.mail_ssl_tls,
        USE_CREDENTIALS=settings.mail_use_credentials,
        VALIDATE_CERTS=settings.mail_validate_certs,
    )
    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=body,
        subtype=MessageType.html,
    )
    await FastMail(config).send_message(message)


def verification_email_body(code: str) -> str:
    return f"""
    <p>Welcome to Lux.</p>
    <p>Your verification code is:</p>
    <h2>{code}</h2>
    <p>This code expires soon.</p>
    """


def password_reset_email_body(code: str) -> str:
    return f"""
    <p>You requested a Lux password reset.</p>
    <p>Your reset code is:</p>
    <h2>{code}</h2>
    <p>This code expires soon. Ignore this email if you did not request it.</p>
    """


def account_banned_email_body() -> str:
    return """
    <p>Your Lux account has been banned.</p>
    <p>If you believe this was a mistake, please contact support.</p>
    """


def account_reactivated_email_body() -> str:
    return """
    <p>Your Lux account has been reactivated.</p>
    <p>You can now sign in and use your account again.</p>
    """
