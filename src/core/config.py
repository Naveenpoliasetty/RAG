from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Resume API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "API for resume data management"
    
    MONGODB_URI: str = "mongodb://localhost:27017/"
    MONGODB_DATABASE: str = "resumes_db"
    MONGODB_COLLECTION: str = "resumes"
    
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    class Config:
        env_file = ".env"

settings = Settings()