from datetime import timedelta
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application configuration.

    For now we only have a few basic settings, but we keep it in a dedicated
    class so that in the future you can easily move to environment variables
    and different configs for dev / prod.
    """

    # SQLite database in the project root by default.
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    SQLITE_DB_PATH: Path = BASE_DIR / "hyperliquid.db"
    DATABASE_URL: str = f"sqlite:///{SQLITE_DB_PATH}"

    # In the future, when moving to Postgres, this can become something like:
    # DATABASE_URL: str = "postgresql+psycopg://user:password@localhost:5432/dbname"

    # Example risk / backtest defaults (can be overridden later)
    DEFAULT_MAX_DRAWDOWN_PCT: float = 0.3
    DEFAULT_BACKTEST_LOOKBACK_DAYS: int = 30
    SIGNAL_LOOKBACK_WINDOW: timedelta = timedelta(minutes=5)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


