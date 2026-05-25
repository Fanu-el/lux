from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exception_handlers import (
    http_exception_handler,
    integrity_error_handler,
    sqlalchemy_error_handler,
    unexpected_error_handler,
    validation_exception_handler,
)
from app.db.session import SessionLocal, engine
from app.models import Base
from app.routes import admin, auth, chats, users
from app.schemas.response import ApiResponse, success_response
from app.services.role_service import seed_default_roles, seed_default_super_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_roles(db)
        seed_default_super_admin(db)
    yield


app = FastAPI(title="Lux API", lifespan=lifespan)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(chats.router)
app.include_router(users.router)


@app.get("/health", response_model=ApiResponse[dict[str, str]])
def health_check():
    return success_response({"status": "ok"})
