"""Automatic model detector - finds the first working Gemini model"""
import logging
from typing import Optional
from google import genai

logger = logging.getLogger(__name__)

# Models to try in order of preference
MODELS_TO_TRY = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-pro-latest",
    "gemini-flash-latest",
]

def detect_working_model(api_key: str) -> Optional[str]:
    """
    Automatically test models and return the first one that works.
    
    Returns:
        str: First working model name, or None if all fail
    """
    client = genai.Client(api_key=api_key)
    
    logger.info("🔍 Detecting working Gemini models...")
    
    for model in MODELS_TO_TRY:
        try:
            logger.info(f"Testing {model}...")
            
            # Try a simple text generation request
            response = client.models.generate_content(
                model=model,
                contents="Say 'OK' in one word only."
            )
            
            # If we get here, it worked!
            logger.info(f"✅ {model} WORKS!")
            return model
            
        except Exception as e:
            error_str = str(e)
            logger.info(f"✗ {model}: {error_str[:100]}")
            continue
    
    logger.warning("❌ No working models found! Using fallback: gemini-pro")
    return "gemini-pro"  # Fallback
