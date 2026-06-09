"""Typed application configuration.

A single ``Settings`` object (pydantic-settings) is the one place the app reads
its environment. Centralizing config means values are parsed/validated once at
startup (a bad ``RECENT_WINDOW_LIMIT`` fails fast and loudly) instead of being
re-parsed with ``os.getenv`` scattered across modules. Field names map to
upper-case env vars (``database_url`` <- ``DATABASE_URL``).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # Connection string for Postgres. Compose builds this from POSTGRES_*; the
    # default targets the compose service so a fresh `docker compose up` works.
    database_url: str = "postgresql://wiki:change-me@postgres:5432/wiki"

    # How many recent rows the dashboard fetches before filtering/sorting in the
    # app. Bounds dashboard cost on a table the firehose will grow. Sized larger
    # than ``feed_page_size`` so the infinite-scroll feed has older rows to load.
    recent_window_limit: int = 500

    # Rows rendered in the initial feed and per infinite-scroll page request.
    feed_page_size: int = 100

    # Pool sizing + fail-fast timeouts so a missing/slow DB degrades to a 503
    # warm-up response instead of hanging a request.
    pool_min_size: int = 1
    pool_max_size: int = 5
    db_timeout_seconds: float = 3.0
    db_connect_timeout: int = 3


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (constructed once, cached)."""

    return Settings()
