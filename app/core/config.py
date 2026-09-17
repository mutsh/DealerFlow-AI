from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Dealer After-Sales AI"
    environment: str = "development"
    model_id: str = "Qwen/Qwen2.5-1.5B-Instruct"
    database_path: str = "data/dealer_agent.db"
    trace_path: str = "data/traces.jsonl"
    manager_api_key: str = "change-me"
    public_base_url: str = "http://localhost:8000"
    twilio_auth_token: str = ""
    ai_disclosure: str = (
        "Hi, I am the dealership's AI service assistant. "
        "I can help with service prices, availability and bookings."
    )
    max_agent_steps: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()
