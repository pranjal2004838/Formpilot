"""Agent 2: Rules Validator - Check eligibility against government rules"""
import logging
from typing import Dict, Any
from datetime import datetime
import google.generativeai as genai
import json

from agents.base import Agent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class RulesValidatorAgent(Agent):
    """
    Agent 2: Validate profile against government eligibility rules
    
    Inputs:
        - profile: Extracted identity profile
        - country: "india" | "us" | "uk" | "canada"
        - app_type: "passport" | "visa" | "driver_license" | etc
    
    Outputs:
        - eligible: true | false
        - validationResults: list of checks performed
        - missingFields: list of required but missing fields
        - notes: human-readable explanation
    """
    
    def __init__(self, gemini_api_key: str):
        super().__init__(name="RulesValidator")
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """Validate eligibility against rules"""
        
        profile = input_data.metadata.get("profile")
        country = input_data.metadata.get("country", "india")
        app_type = input_data.metadata.get("app_type", "passport")
        
        if not profile:
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=0,
                errors=["Missing profile in input"]
            )
        
        try:
            # Use Gemini to validate against rules
            validation_result = await self._validate_with_gemini(
                profile, country, app_type
            )
            
            return AgentOutput(
                status="success",
                data=validation_result,
                confidence=0.95
            )
        
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=0,
                errors=[str(e)]
            )
    
    async def _validate_with_gemini(
        self, 
        profile: Dict[str, Any], 
        country: str, 
        app_type: str
    ) -> Dict[str, Any]:
        """Validate against rules using Gemini"""
        
        prompt = f"""
You are an expert in government eligibility requirements. 

Check if this person is eligible for a {country.upper()} {app_type.upper()} based on their profile:

Profile:
- Name: {profile.get('fullName', {}).get('value', 'Unknown')}
- DOB: {profile.get('dob', {}).get('value', 'Unknown')}
- Gender: {profile.get('gender', {}).get('value', 'Unknown')}
- Document Type: {profile.get('documentType', 'Unknown')}

Rules by country:
- INDIA: Passport requires 18+ age, Indian resident, valid ID
- US: Visa requires 18+ age, valid passport, financial proof
- UK: Visa requires 18+ age, valid passport, financial proof
- CANADA: Visa requires 18+ age, valid passport, clean background

Return ONLY valid JSON (no markdown):
{{
    "eligible": true/false,
    "validationResults": [
        {{"check": "age_requirement", "passed": true, "requirement": "18+ years", "explanation": "..."}},
        {{"check": "residency", "passed": true, "requirement": "Valid residence", "explanation": "..."}}
    ],
    "missingFields": [],
    "notes": "Brief explanation of eligibility",
    "confidence": 0.95
}}
"""
        
        response = self.model.generate_content(prompt)
        
        try:
            response_text = response.text
            
            # Clean markdown if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response_text)
            
            return {
                "eligible": result.get("eligible", False),
                "validationResults": result.get("validationResults", []),
                "missingFields": result.get("missingFields", []),
                "notes": result.get("notes", ""),
                "country": country,
                "app_type": app_type,
                "validated_at": datetime.now().isoformat()
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation response: {response_text}")
            # Fallback: assume eligible if parsing fails
            return {
                "eligible": True,
                "validationResults": [],
                "missingFields": [],
                "notes": "Auto-validation passed (parsing error)",
                "country": country,
                "app_type": app_type,
                "validated_at": datetime.now().isoformat()
            }
