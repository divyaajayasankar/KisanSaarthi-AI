from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KisanSaarthi AI"

    # Phase-1 local database
    database_url: str = "sqlite:///./kisansaarthi.db"

    # Allow software-only demonstration data
    allow_test_data: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()