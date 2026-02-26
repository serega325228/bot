from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    REDIS_HOST: str
    REDIS_PORT: int
    WAIT_TIMER_SECONDS: int = 180
    BOARDED_GRACE_SECONDS: int = 30
    STOP_RADIUS_METERS: int = 50
    BOT_TOKEN: str
    GPS_DEBOUNCE_SECONDS: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

settings = Settings()
