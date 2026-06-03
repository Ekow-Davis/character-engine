from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Supabase
    database_url: str

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Anthropic
    anthropic_api_key: str

    # OpenAI
    openai_api_key: str

    # Resend
    resend_api_key: str
    resend_from_email: str
    owner_email: str

    # App
    app_env: str = "development"
    app_secret_key: str
    frontend_url: str = "http://localhost:5173"

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


settings = Settings()
