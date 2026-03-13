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
    APP_VERSION: str = "1.0.0"
    
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
    
    # Slack Webhook (Optional - for notifications)
    SLACK_WEBHOOK_URL: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Document Analysis Settings
    MAX_DOCUMENT_SIZE_MB: int = 10
    SUPPORTED_IMAGE_FORMATS: list = ["jpg", "jpeg", "png", "pdf", "bmp", "gif", "webp"]
    
    # Gemini API Settings
    GEMINI_MODEL_VISION: str = "gemini-pro-vision"
    GEMINI_MODEL_TEXT: str = "gemini-pro"
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
