from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SESSIONGRID_",
        extra="ignore",
    )

    app_name: str = "SessionGrid"
    env: str = "development"
    database_url: str = "sqlite:///./sessiongrid.db"
    runtime_dir: str = "./runtime_data"
    headless: bool = True
    screenshot_quality: int = 65
    default_start_url: str = "https://example.com"

    @property
    def runtime_path(self) -> Path:
        path = Path(self.runtime_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
