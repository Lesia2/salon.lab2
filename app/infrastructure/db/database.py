"""Підключення до MySQL і сесії SQLAlchemy."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.infrastructure.config import settings

engine = create_engine(settings.database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session():
    """Одна сесія на HTTP-запит."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
