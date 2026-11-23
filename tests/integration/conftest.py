"""Спільні налаштування integration-тестів.

Тести працюють з окремою базою salon_test (TEST_DB_NAME у .env),
тому робочі дані в базі salon не зачіпаються.
"""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.entities import Role
from app.infrastructure.config import settings
from app.infrastructure.db.database import Base, get_session
from app.infrastructure.db.orm_models import ClientORM, ScheduleORM, SpecialistORM
from app.infrastructure.security import BcryptPasswordHasher, JwtTokenService
from app.main import app

test_engine = create_engine(settings.database_url(settings.test_db_name), pool_pre_ping=True)
TestSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Один раз на всі тести: створюємо таблиці в salon_test."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def clean_tables():
    """Перед кожним тестом очищаємо таблиці, щоб тести не впливали один на одного."""
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture
def db():
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def api():
    """HTTP-клієнт, у якому залежність get_session підмінена на тестову базу."""

    def override_get_session():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    # Без «with»: подія старту (створення таблиць у робочій БД) не запускається
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------- Користувачі ----------

def _create_user(db, email: str, role: Role) -> ClientORM:
    user = ClientORM(
        name="Тест",
        email=email,
        phone="+380671234567",
        password_hash=BcryptPasswordHasher().hash("secret123"),
        role=role,
    )
    db.add(user)
    db.commit()
    return user


def _auth_header(user: ClientORM) -> dict:
    return {"Authorization": f"Bearer {JwtTokenService().create(user.id)}"}


@pytest.fixture
def client_user(db):
    return _create_user(db, "client@example.com", Role.client)


@pytest.fixture
def other_user(db):
    return _create_user(db, "other@example.com", Role.client)


@pytest.fixture
def admin_user(db):
    return _create_user(db, "admin@example.com", Role.admin)


@pytest.fixture
def client_headers(client_user):
    return _auth_header(client_user)


@pytest.fixture
def other_headers(other_user):
    return _auth_header(other_user)


@pytest.fixture
def admin_headers(admin_user):
    return _auth_header(admin_user)


# ---------- Майстер з графіком ----------

@pytest.fixture
def specialist(db):
    """Активний майстер, який працює щодня з 09:00 до 18:00."""
    spec = SpecialistORM(name="Оксана", specialization="перукар", is_active=True)
    db.add(spec)
    db.flush()
    for weekday in range(7):
        db.add(
            ScheduleORM(
                specialist_id=spec.id,
                weekday=weekday,
                start_time=datetime.strptime("09:00", "%H:%M").time(),
                end_time=datetime.strptime("18:00", "%H:%M").time(),
            )
        )
    db.commit()
    return spec


@pytest.fixture
def future_day() -> date:
    """День через тиждень — гарантовано в майбутньому."""
    return date.today() + timedelta(days=7)


def at(day: date, hhmm: str) -> str:
    """Допоміжна функція: дата + час у форматі ISO для запитів."""
    return f"{day.isoformat()}T{hhmm}:00"
