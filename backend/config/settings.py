"""Configuration management for FormPilot"""
import os
from typing import Optional

class Settings:
    """Application settings loaded from environment"""
    
    # API Configuration
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # Server Configuration
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    APP_NAME: str = "FormPilot Enterprise API"
    APP_VERSION: str = "2.0.0"
    
    # CORS Configuration
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    ALLOWED_ORIGINS: list = [
        FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000"
    ]
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./formpilot.db")
    
    # AWS S3 Configuration (Optional)
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_S3_BUCKET: Optional[str] = os.getenv("AWS_S3_BUCKET")
    
    # ──────────────────────────────────────────────────────────────
    # Airia Platform Integration
    # ──────────────────────────────────────────────────────────────
    AIRIA_API_KEY: Optional[str] = os.getenv("AIRIA_API_KEY")
    AIRIA_PIPELINE_ID: Optional[str] = os.getenv("AIRIA_PIPELINE_ID")
    AIRIA_BASE_URL: str = os.getenv("AIRIA_BASE_URL", "https://api.airia.io")

    # FormPilot API (base URL + key for Airia tool call-back)
    FORMPILOT_API_URL: str = os.getenv("FORMPILOT_API_URL", "http://localhost:8000")
    FORMPILOT_API_KEY: Optional[str] = os.getenv("FORMPILOT_API_KEY")

    # ──────────────────────────────────────────────────────────────
    # Slack Integration
    # ──────────────────────────────────────────────────────────────
    SLACK_WEBHOOK_URL: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
    SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "#formpilot-notifications")

    # ──────────────────────────────────────────────────────────────
    # SharePoint / Microsoft Graph Integration
    # ──────────────────────────────────────────────────────────────
    SHAREPOINT_TENANT_ID: Optional[str] = os.getenv("SHAREPOINT_TENANT_ID")
    SHAREPOINT_CLIENT_ID: Optional[str] = os.getenv("SHAREPOINT_CLIENT_ID")
    SHAREPOINT_CLIENT_SECRET: Optional[str] = os.getenv("SHAREPOINT_CLIENT_SECRET")
    SHAREPOINT_SITE_URL: Optional[str] = os.getenv("SHAREPOINT_SITE_URL")
    SHAREPOINT_LIBRARY: str = os.getenv("SHAREPOINT_LIBRARY", "FormPilot Documents")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Document Analysis Settings
    MAX_DOCUMENT_SIZE_MB: int = 10
    SUPPORTED_IMAGE_FORMATS: list = ["jpg", "jpeg", "png", "pdf", "bmp", "gif", "webp"]
    
    # Gemini API Settings
    GEMINI_MODEL_VISION: str = "gemini-3-flash"
    GEMINI_MODEL_TEXT: str = "gemini-3-flash"
    GEMINI_TEMPERATURE: float = 0.3  # Lower for more consistent results
    GEMINI_MAX_TOKENS: int = 1024
    
    # Validation Settings
    MIN_CONFIDENCE_FOR_AUTO_FILL: float = 0.7
    REQUIRE_SECOND_OPINION: bool = False  # Require validation for high-stakes forms
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        if not cls.GEMINI_API_KEY and not cls.ANTHROPIC_API_KEY:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "No AI API key configured. Set GEMINI_API_KEY or ANTHROPIC_API_KEY in .env"
            )
        return True


# Create settings instance
settings = Settings()
