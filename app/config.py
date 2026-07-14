from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/marketing"
    redis_url: str = "redis://localhost:6379"

    twenty_base_url: str = "http://localhost:3000/rest"
    twenty_api_key: str = ""

    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "EMPTY"
    llm_model_name: str = "qwen3.6-35b-a3b"
    mirrorfit_mode: bool = True

    apollo_api_key: str = ""
    apify_api_token: str = ""
    coresignal_api_key: str = ""

    mailchimp_api_key: str = ""
    brevo_api_key: str = ""
    email_provider: str = "mailchimp"
    email_from: str = "Marketing <marketing@yourdomain.com>"
    email_from_name: str = "Marketing"
    email_reply_to: str = ""

    email_max_per_hour: int = 50
    email_min_delay_seconds: int = 180
    email_daily_cap: int = 200

    app_secret: str = "change-me"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
