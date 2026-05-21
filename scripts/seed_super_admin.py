import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal, engine
from app.core.config import settings
from app.models import Base
from app.models.user import User
from app.services.role_service import seed_default_roles, seed_default_super_admin


def main() -> None:
    if not settings.super_admin_email or not settings.super_admin_password:
        print("Missing SUPER_ADMIN_EMAIL or SUPER_ADMIN_PASSWORD in .env.")
        return

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_default_roles(db)
        email = settings.super_admin_email.lower().strip()
        if _user_exists(db, email):
            print("Super admin user already exists.")
            return

        seed_default_super_admin(db)

    print("Super admin user seeded successfully.")


def _user_exists(db, email: str) -> bool:
    return db.query(User).filter(User.email == email).one_or_none() is not None


if __name__ == "__main__":
    main()
