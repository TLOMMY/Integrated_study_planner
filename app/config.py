from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 120
    database_url: str = "sqlite:///./study_planner.db"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()