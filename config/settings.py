"""
Configuration settings for Unilever Procurement GPT POC
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "unilever_poc"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""

    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4o-harshal"
    AZURE_OPENAI_MODEL: str = "gpt-4o"
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"

    # LLM Provider Configuration
    AGENT_LLM_PROVIDER: str = "azure"  # "azure" or "ollama"
    EVALUATOR_LLM_PROVIDER: str = "azure"  # "azure" or "ollama"

    # Ollama Configuration (Backup)
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True

    # Dashboard Configuration
    DASHBOARD_PORT: int = 8501

    # Logging
    LOG_LEVEL: str = "INFO"

    # Redis Configuration (Optional)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Alert Configuration
    ALERT_EMAIL_ENABLED: bool = False
    ALERT_SLACK_ENABLED: bool = False
    ALERT_SLACK_WEBHOOK_URL: Optional[str] = None

    # Evaluation Configuration
    EVALUATION_THRESHOLD: float = 0.7
    DRIFT_HIGH_THRESHOLD: float = 0.5
    DRIFT_MEDIUM_THRESHOLD: float = 0.3

    # Embedding Configuration
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    @property
    def database_url(self) -> str:
        """Get database connection URL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def async_database_url(self) -> str:
        """Get async database connection URL"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
