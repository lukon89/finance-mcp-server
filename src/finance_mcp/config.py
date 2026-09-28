from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OAuth
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_redirect_uri: str = "http://localhost:8000/auth/callback"

    # JWT
    jwt_secret: str = Field(default="dev-secret-change-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # HTTP Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Database
    db_path: str = "finance.db"

    # Rate limiting
    rate_limit_per_minute: int = 60

    # External APIs
    frankfurter_base_url: str = "https://api.frankfurter.app"
    exchange_rate_cache_ttl: int = 3600  # seconds


settings = Settings()
