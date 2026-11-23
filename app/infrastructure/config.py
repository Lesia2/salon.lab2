"""Налаштування застосунку. Значення читаються з файлу .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "salon"
    test_db_name: str = "salon_test"

    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 60

    # Адміністратор, який створюється автоматично під час старту
    admin_email: str | None = None
    admin_password: str | None = None

    def database_url(self, db_name: str | None = None) -> URL:
        # URL.create сам екранує спецсимволи в паролі (@, :, / тощо)
        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=db_name or self.db_name,
            query={"charset": "utf8mb4"},
        )


settings = Settings()
