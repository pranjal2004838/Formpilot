"""Agent 2: Rules Validator - Check eligibility against government rules"""
import logging
from typing import Dict, Any
from datetime import datetime
import google.generativeai as genai
import json

from agents.base import Agent, AgentInput, AgentOutput
from compliance.rule_engine import evaluate_compliance

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
        self.model_name = "gemini-pro"
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """Validate eligibility against rules"""
        
        profile = input_data.metadata.get("profile")
        country = input_data.metadata.get("country", "IN")
        app_type = input_data.metadata.get("app_type", "passport")
        document_type = (
            input_data.metadata.get("document_type")
            or profile.get("documentType")
            or "generic"
        )
        
        if not profile:
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=0,
                errors=["Missing profile in input"]
            )
        
        try:
            validation_result = evaluate_compliance(
                profile=profile,
                country=country,
                app_type=app_type,
                document_type=document_type,
            )

            # Add optional Gemini risk narrative without changing deterministic pass/fail logic.
            try:
                ai_review = await self._validate_with_gemini(
                    profile,
                    country,
                    app_type,
                    document_type,
                    validation_result,
                )
                if ai_review:
                    validation_result["aiReview"] = ai_review
            except Exception as ai_error:
                logger.warning("Gemini review unavailable, deterministic checks used: %s", ai_error)
            
            return AgentOutput(
                status="success",
                data=validation_result,
                confidence=max(float(validation_result.get("complianceScore", 0)) / 100.0, 0.80),
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
        app_type: str,
        document_type: str,
        deterministic_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a concise AI risk narrative for reviewer context."""
        
        prompt = f"""
You are a government compliance analyst.

Review this applicant and provide ONLY additional risk context.
Do not recompute eligibility.

Profile:
- Name: {profile.get('fullName', {}).get('value', 'Unknown')}
- DOB: {profile.get('dob', {}).get('value', 'Unknown')}
- Gender: {profile.get('gender', {}).get('value', 'Unknown')}
- Document Type: {document_type}

Deterministic compliance output:
{json.dumps(deterministic_result, indent=2)}

Return ONLY valid JSON (no markdown):
{{
  "summary": "One sentence reviewer summary",
  "additionalRisks": [
    {{"risk": "...", "severity": "low|medium|high", "rationale": "..."}}
  ],
  "recommendedReviewAction": "approve|manual_review|reject"
}}
"""
        
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            response_text = response.text
            
            # Clean markdown if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response_text)

            return {
                "summary": result.get("summary", "AI review completed."),
                "additionalRisks": result.get("additionalRisks", []),
                "recommendedReviewAction": result.get("recommendedReviewAction", "manual_review"),
                "generated_at": datetime.now().isoformat(),
                "country": str(country).upper(),
                "app_type": app_type,
            }
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation response: {response_text}")
            raise Exception(f"Invalid JSON from Gemini review: {e}")

    @staticmethod
    def _response_text(response: Any) -> str:
        text = (getattr(response, "text", None) or "").strip()
        if text:
            return text

        candidates = getattr(response, "candidates", None) or []
        chunks = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if not parts:
                continue
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    chunks.append(part_text)

        text = "\n".join(chunks).strip()
        if not text:
            raise Exception("Empty response from Gemini model")
        return text
