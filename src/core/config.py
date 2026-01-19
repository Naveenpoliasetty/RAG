from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    # ============================
    # App Settings
    # ============================
    APP_NAME: str = "Resume API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "API for resume data management"

    # ============================
    # MongoDB Config
    # ============================
    MONGODB_URI: str = "mongodb://localhost:27017/"
    MONGODB_DATABASE: str = "resumes_db"
    MONGODB_COLLECTION: str = "resumes"

    # ============================
    # CORS Config
    # ============================
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ============================
    # Qdrant / OpenAI / ZenML Settings
    # (This is what was missing)
    # ============================
    openai_api_key: str = ""
    gemini_api_keys: List[str] = []
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    zenml_port: int = 8080

    # ============================
    # Pydantic v2 Config
    # ============================
    model_config = {
        "extra": "allow",       # This prevents extra_forbidden errors
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }


# Singleton settings object
settings = Settings()