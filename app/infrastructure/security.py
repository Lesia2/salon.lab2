"""Технічні реалізації: хешування паролів (bcrypt), JWT-токени, системний годинник."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.domain.ports import Clock, PasswordHasher
from app.infrastructure.config import settings

ALGORITHM = "HS256"


class BcryptPasswordHasher(PasswordHasher):
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now().replace(microsecond=0)


class InvalidToken(Exception):
    pass


class JwtTokenService:
    def __init__(self, secret: str = settings.jwt_secret, expire_minutes: int = settings.jwt_expire_minutes):
        self._secret = secret
        self._expire_minutes = expire_minutes

    def create(self, client_id: int) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self._expire_minutes)
        return jwt.encode({"sub": str(client_id), "exp": expire}, self._secret, algorithm=ALGORITHM)

    def read_client_id(self, token: str) -> int:
        """Повертає id користувача з токена або кидає InvalidToken з поясненням."""
        try:
            payload = jwt.decode(token, self._secret, algorithms=[ALGORITHM])
            return int(payload["sub"])
        except jwt.ExpiredSignatureError:
            raise InvalidToken("Термін дії токена минув")
        except (jwt.InvalidTokenError, KeyError, ValueError):
            raise InvalidToken("Невалідний токен")
