import os
from functools import lru_cache


def _load_env_file() -> None:
    if not os.path.exists(".env"):
        return

    with open(".env", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env_file()


class Settings:
    app_name: str = os.getenv("APP_NAME", "Lux")
    _raw_database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/lux",
    )
    database_url: str = (
        _raw_database_url.replace("postgres://", "postgresql+psycopg://")
        if _raw_database_url.startswith("postgres://")
        else _raw_database_url.replace("postgresql://", "postgresql+psycopg://")
    )
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )
    super_admin_name: str | None = os.getenv("SUPER_ADMIN_NAME")
    super_admin_email: str | None = os.getenv("SUPER_ADMIN_EMAIL")
    super_admin_password: str | None = os.getenv("SUPER_ADMIN_PASSWORD")
    mail_username: str | None = os.getenv("MAIL_USERNAME")
    mail_password: str | None = os.getenv("MAIL_PASSWORD")
    mail_from: str | None = os.getenv("MAIL_FROM")
    mail_from_name: str = os.getenv("MAIL_FROM_NAME", "Lux")
    mail_server: str = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    mail_port: int = int(os.getenv("MAIL_PORT", "587"))
    mail_starttls: bool = os.getenv("MAIL_STARTTLS", "true").lower() == "true"
    mail_ssl_tls: bool = os.getenv("MAIL_SSL_TLS", "false").lower() == "true"
    mail_use_credentials: bool = (
        os.getenv("MAIL_USE_CREDENTIALS", "true").lower() == "true"
    )
    mail_validate_certs: bool = (
        os.getenv("MAIL_VALIDATE_CERTS", "true").lower() == "true"
    )
    verification_code_expires_in_minute: int = int(
        os.getenv("VERIFICATION_CODE_EXPIRES_IN_MINUTE", "10")
    )
    password_reset_code_expires_in_minute: int = int(
        os.getenv("PASSWORD_RESET_CODE_EXPIRES_IN_MINUTE", "10")
    )
    verification_code_resend_cooldown_seconds: int = int(
        os.getenv("VERIFICATION_CODE_RESEND_COOLDOWN_SECONDS", "60")
    )
    verification_code_length: int = int(os.getenv("VERIFICATION_CODE_LENGTH", "6"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
