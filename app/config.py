from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KisanSaarthi AI"

    # Phase-1 local database
    database_url: str = "sqlite:///./kisansaarthi.db"

    # Allow software-only demonstration data
    allow_test_data: bool = True

    # --------------------------------------------------------
    # Decision controller (ANSWER / ASK_FOLLOW_UP / ABSTAIN)
    # --------------------------------------------------------
    # Image evidence at or above vision_answer_threshold may
    # drive an advisory. Between the two thresholds the farmer
    # is asked to confirm. Below vision_ask_threshold the
    # visual evidence is rejected.
    vision_answer_threshold: float = 0.80
    vision_ask_threshold: float = 0.55

    # Maximum follow-up questions before the assistant abstains.
    max_follow_up_turns: int = 6

    # --------------------------------------------------------
    # Optional LLM (Mode A). Absent key -> deterministic Mode B.
    # Any OpenAI-compatible chat-completions endpoint works.
    # --------------------------------------------------------
    llm_enabled: bool = False
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 20.0

    # --------------------------------------------------------
    # Speech-to-text (faster-whisper, CPU)
    # --------------------------------------------------------
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    max_audio_mb: int = 20

    # --------------------------------------------------------
    # Conversation storage
    # --------------------------------------------------------
    conversation_ttl_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    @property
    def llm_active(self) -> bool:
        return bool(self.llm_enabled and self.llm_api_key.strip())


settings = Settings()
