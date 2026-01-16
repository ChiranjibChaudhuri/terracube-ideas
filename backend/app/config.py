from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PORT: int = 4000
    DATABASE_URL: str
    JWT_SECRET: str
    CORS_ORIGIN: str = "http://localhost:5173"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # MinIO
    MINIO_ENDPOINT: str = "localhost"
    MINIO_PORT: int = 9000
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "ideas-staging"
    
    # Admin
    ADMIN_EMAIL: str = "admin@terracube.geo"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_NAME: str = "System Admin"

    # GEBCO
    GEBCO_URL: Optional[str] = None
    GEBCO_MAX_IMAGE_PIXELS: int = 8000000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
