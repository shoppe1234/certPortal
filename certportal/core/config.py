"""certportal/core/config.py — Application settings via pydantic-settings.

All settings load from environment variables or .env file.
No hardcoded secrets anywhere in the codebase.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OVHcloud Object Storage (S3-compatible)
    ovh_s3_endpoint: str
    ovh_s3_key: str
    ovh_s3_secret: str
    ovh_s3_region: str
    ovh_s3_workspace_bucket: str = "certportal-workspaces"
    ovh_s3_raw_edi_bucket: str = "certportal-raw-edi"

    # PostgreSQL
    certportal_db_url: str

    # OpenAI
    openai_api_key: str

    # JWT
    certportal_jwt_secret: str

    # Slack (optional — agents fail gracefully if absent)
    slack_certportal_ui_webhook: str | None = None
    slack_certportal_ops_webhook: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
