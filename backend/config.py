"""Configuration management for the regulatory analytics tool."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    openrouter_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str = "https://openrouter.ai/api/v1"
    no_llm: bool = Field(False, env="REG_ATLAS_NO_LLM")
    
    # Application Settings
    log_level: str = "INFO"
    data_dir: Path = Path("./data")
    chroma_persist_dir: Path = Path("./data/db/chroma")
    max_upload_mb: int = 20
    max_query_results: int = 15
    default_query_results: int = 5
    
    # Model Configuration
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "openai/gpt-3.5-turbo"  # OpenRouter uses provider/model format
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
