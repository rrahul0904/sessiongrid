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

    # Control-plane bootstrap. Local development stays frictionless while
    # production can require a scoped API key until OIDC/SSO is wired in.
    auth_required: bool = False
    auto_create_schema: bool = True
    bootstrap_admin_email: str = "admin@sessiongrid.local"
    bootstrap_admin_name: str = "Local Admin"
    bootstrap_api_key: str | None = None
    default_organization_name: str = "SessionGrid Demo"
    default_organization_slug: str = "sessiongrid-demo"
    default_workspace_name: str = "Default Workspace"

    @property
    def runtime_path(self) -> Path:
        path = Path(self.runtime_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
