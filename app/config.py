from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional
import os

class Settings(BaseSettings):
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    bot_backend_api_key: str
    
    use_https: bool = Field(False, description="Use HTTPS for serving")
    ssl_keyfile: Optional[str] = Field(None, description="SSL key file path")
    ssl_certfile: Optional[str] = Field(None, description="SSL certificate file path")
    
    bot_token: str
    bot_admin_ids: List[int] = Field(default_factory=list)
    
    mongodb_url: str
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @field_validator('bot_admin_ids', mode='before')
    @classmethod
    def parse_bot_admin_ids(cls, v):
        """Parse BOT_ADMIN_IDS from comma-separated string to list of integers"""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",")]
        return [int(v)]

def get_settings() -> Settings:
    return Settings()