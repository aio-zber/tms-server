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
    database_url: str = Field(..., description="Base PostgreSQL connection URL (will be converted to async)")
    database_url_sync: str = Field(..., description="Sync PostgreSQL connection URL for Alembic")
    
    @property
    def async_database_url(self) -> str:
        """
        Convert the base DATABASE_URL to async format for SQLAlchemy.
        Railway provides postgresql:// but we need postgresql+asyncpg:// for async operations.
        """
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url

    # Redis
    redis_url: str = Field(default="", description="Redis connection URL (optional)")
    redis_password: str = Field(default="", description="Redis password")

    # User Management Integration (GCGC Team Management System)
    user_management_api_url: str = Field(..., description="User Management System (GCGC) API base URL")
    user_management_api_key: str = Field(..., description="User Management System API authentication key")
    user_management_api_timeout: int = Field(default=30, description="User Management API request timeout in seconds")

    # Security
    jwt_secret: str = Field(..., min_length=32, description="JWT secret key (min 32 chars)")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_hours: int = Field(default=24, description="JWT expiration time in hours")
    nextauth_secret: str = Field(..., min_length=32, description="NextAuth secret key from GCGC TMS (same as NEXTAUTH_SECRET)")

    # CORS (string will be converted to list by validator)
    allowed_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins"
    )
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1",
        description="Comma-separated list of allowed hosts"
    )

    # Alibaba Cloud OSS (Optional for basic functionality)
    oss_access_key_id: str = Field(default="", description="Alibaba Cloud OSS Access Key ID")
    oss_access_key_secret: str = Field(default="", description="Alibaba Cloud OSS Access Key Secret")
    oss_bucket_name: str = Field(default="", description="OSS bucket name")
    oss_endpoint: str = Field(default="oss-cn-hangzhou.aliyuncs.com", description="OSS endpoint")
    oss_region: str = Field(default="cn-hangzhou", description="OSS region")

    # File Upload
    max_upload_size: int = Field(default=104857600, description="Max file upload size in bytes (100MB)")
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

    def get_allowed_origins_list(self) -> List[str]:
        """Get allowed origins as a list."""
        if isinstance(self.allowed_origins, list):
            return self.allowed_origins
        if isinstance(self.allowed_origins, str):
            return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        return ["http://localhost:3000"]

    def get_tms_client_url(self) -> str:
        """
        Get TMS-Client URL without trailing slash.

        Security Note: This URL is used as the redirect_uri in SSO flows.
        It's derived from the first allowed origin (not user-supplied) to prevent
        open redirect attacks where attackers could steal SSO codes.

        Returns:
            First allowed origin URL without trailing slash
        """
        origins = self.get_allowed_origins_list()
        if origins:
            return origins[0].rstrip('/')
        return "http://localhost:3000"

    def get_allowed_hosts_list(self) -> List[str]:
        """Get allowed hosts as a list."""
        if isinstance(self.allowed_hosts, list):
            return self.allowed_hosts
        if isinstance(self.allowed_hosts, str):
            return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]
        return ["localhost", "127.0.0.1"]
    
    def get_allowed_file_types_list(self) -> List[str]:
        """Get allowed file types as a list."""
        if isinstance(self.allowed_file_types, list):
            return self.allowed_file_types
        if isinstance(self.allowed_file_types, str):
            return [ft.strip() for ft in self.allowed_file_types.split(",") if ft.strip()]
        return ["image/jpeg", "image/png", "image/gif", "application/pdf"]

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
