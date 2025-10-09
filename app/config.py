"""
Application configuration using Pydantic Settings.
Loads configuration from environment variables with validation.
"""
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Environment
    environment: str = Field(default="development", description="Environment: development, staging, production")
    debug: bool = Field(default=False, description="Debug mode")

    # Database
    database_url: str = Field(..., description="Async PostgreSQL connection URL")
    database_url_sync: str = Field(..., description="Sync PostgreSQL connection URL for Alembic")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    redis_password: str = Field(default="", description="Redis password")

    # TMS Integration
    tms_api_url: str = Field(..., description="TMS API base URL")
    tms_api_key: str = Field(..., description="TMS API authentication key")
    tms_api_timeout: int = Field(default=30, description="TMS API request timeout in seconds")

    # Security
    jwt_secret: str = Field(..., min_length=32, description="JWT secret key (min 32 chars)")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_hours: int = Field(default=24, description="JWT expiration time in hours")

    # CORS
    allowed_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins"
    )
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1",
        description="Comma-separated list of allowed hosts"
    )

    # Alibaba Cloud OSS
    oss_access_key_id: str = Field(..., description="Alibaba Cloud OSS Access Key ID")
    oss_access_key_secret: str = Field(..., description="Alibaba Cloud OSS Access Key Secret")
    oss_bucket_name: str = Field(..., description="OSS bucket name")
    oss_endpoint: str = Field(default="oss-cn-hangzhou.aliyuncs.com", description="OSS endpoint")
    oss_region: str = Field(default="cn-hangzhou", description="OSS region")

    # File Upload
    max_upload_size: int = Field(default=10485760, description="Max file upload size in bytes (10MB)")
    allowed_file_types: str = Field(
        default="image/jpeg,image/png,image/gif,application/pdf",
        description="Comma-separated list of allowed MIME types"
    )

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=100, description="API rate limit per minute per user")
    rate_limit_per_hour: int = Field(default=1000, description="API rate limit per hour per user")

    # WebSocket
    ws_heartbeat_interval: int = Field(default=30, description="WebSocket heartbeat interval in seconds")
    ws_max_connections: int = Field(default=10000, description="Maximum concurrent WebSocket connections")

    # Cache TTL (in seconds)
    cache_user_ttl: int = Field(default=600, description="User cache TTL in seconds")
    cache_presence_ttl: int = Field(default=300, description="Presence cache TTL in seconds")
    cache_session_ttl: int = Field(default=86400, description="Session cache TTL in seconds")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")

    # Sentry (Optional)
    sentry_dsn: str = Field(default="", description="Sentry DSN for error tracking")
    sentry_environment: str = Field(default="development", description="Sentry environment")

    @field_validator("allowed_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    @field_validator("allowed_hosts")
    @classmethod
    def parse_allowed_hosts(cls, v: str) -> List[str]:
        """Parse comma-separated allowed hosts into a list."""
        return [host.strip() for host in v.split(",") if host.strip()]

    @field_validator("allowed_file_types")
    @classmethod
    def parse_file_types(cls, v: str) -> List[str]:
        """Parse comma-separated file types into a list."""
        return [file_type.strip() for file_type in v.split(",") if file_type.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()
