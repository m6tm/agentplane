"""Application configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agentplane settings."""

    model_config = SettingsConfigDict(env_prefix="AGENTPLANE_", env_file=".env")

    app_name: str = "agentplane"
    debug: bool = False

    # Server
    host: str = "127.0.0.1"
    port: int = 3400

    # Database — SQLite by default for zero-config, low-resource usage
    database_url: str = "sqlite:///./data/agentplane.db"

    # Data directory for local storage
    data_dir: Path = Path("./data")

    # Agent execution
    default_agent_timeout: int = 300  # seconds
    default_grace_period: int = 20  # seconds

    # Logging
    log_level: str = "INFO"
    json_logs: bool = False


settings = Settings()
