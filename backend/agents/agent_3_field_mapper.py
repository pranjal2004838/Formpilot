"""Agent 3: Field Mapper - Map extracted identity to form fields"""
import logging
from typing import Dict, List, Any
from google import genai
import json

from agents.base import Agent, AgentInput, AgentOutput
from fuzzywuzzy import fuzz
from utils.form_mapping import map_profile_to_form_fields

logger = logging.getLogger(__name__)


class FieldMapperAgent(Agent):
    """
    Agent 3: Map extracted identity fields to form fields using semantic matching
    
    Inputs:
        - profile: Extracted identity profile
        - form_fields: List of form field definitions
    
    Outputs:
        - mappings: List of field mappings with values and confidence
        - readyToFill: Boolean indicating if ready to auto-fill
        - confidence_scores: Per-field confidence scores
    """
    
    def __init__(self, gemini_api_key: str):
        super().__init__(name="FieldMapper")
        self.client = genai.Client(api_key=gemini_api_key)
        self.model_name = "gemini-1.5-flash"
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """Map fields using semantic matching"""
        
        profile = input_data.metadata.get("profile")
        form_fields = input_data.metadata.get("form_fields", [])
        country = input_data.metadata.get("country", "")
        app_type = input_data.metadata.get("app_type", "")
        
        if not profile:
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=0,
                errors=["Missing profile in input"]
            )
        
        if not form_fields:
            # If no explicit form fields, create default ones
            form_fields = self._get_default_form_fields()
        
        try:
            # Match fields using Gemini semantic understanding
            mappings = await self._match_fields_with_gemini(profile, form_fields, country=country, app_type=app_type)
            
            # Calculate overall confidence
            if mappings:
                confidence = sum(m.get('confidence', 0) for m in mappings) / len(mappings)
            else:
                confidence = 0
            
            return AgentOutput(
                status="success",
                data={
                    "mappings": mappings,
                    "readyToFill": all(m.get('confidence', 0) > 0.7 for m in mappings) if mappings else False,
                    "confidence_scores": {m['formField']: m.get('confidence', 0) for m in mappings}
                },
                confidence=confidence
            )
        
        except Exception as e:
            logger.error(f"Field mapping failed: {str(e)}", exc_info=True)
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=0,
                errors=[str(e)]
            )
    
    async def _match_fields_with_gemini(
        self, 
        profile: Dict[str, Any], 
        form_fields: List[Dict],
        *,
        country: str = "",
        app_type: str = "",
    ) -> List[Dict]:
        """Match form fields to profile using Gemini semantic understanding"""
        
        # Extract profile data for readability
        profile_data = {
            "fullName": profile.get('fullName', {}).get('value', ''),
            "dob": profile.get('dob', {}).get('value', ''),
            "gender": profile.get('gender', {}).get('value', ''),
            "address": {k: v.get('value', '') for k, v in profile.get('address', {}).items()},
            "documentId": profile.get('documentId', {}).get('value', ''),
            "documentType": profile.get('documentType', ''),
        }
        
        field_catalog = [
            {
                "name": field.get("name", ""),
                "label": field.get("label", ""),
                "type": field.get("type", "text"),
                "placeholder": field.get("placeholder", ""),
                "options": [
                    option.get("label") or option.get("text") or option.get("value")
                    for option in field.get("options", []) or []
                ],
            }
            for field in form_fields
        ]
        
        prompt = f"""
You are an expert at matching form fields to personal data.

I have extracted this person's data:
{json.dumps(profile_data, indent=2)}

And a form with these fields:
{json.dumps(field_catalog, indent=2)}

For EACH form field:
1. Find the best matching data from the profile
2. Transform if needed (e.g., split "John Smith" into firstName="John", lastName="Smith")
3. Provide confidence score (0-1)

Return ONLY valid JSON array with no markdown:
[
    {{
        "formField": "firstName",
        "profileField": "fullName",
        "value": "John",
        "transformation": "split",
        "confidence": 0.98
    }},
    {{
        "formField": "lastName",
        "profileField": "fullName",
        "value": "Smith",
        "transformation": "split",
        "confidence": 0.98
    }},
    ...
]

Use the field `name` as the value of `formField` in your output.
Be comprehensive - include all form fields.
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            response_text = self._response_text(response)
            
            # Clean markdown if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            mappings = json.loads(response_text)
            if not mappings:
                return map_profile_to_form_fields(
                    profile,
                    form_fields,
                    country=country,
                    app_type=app_type,
                )
            
            return mappings
        
        except json.JSONDecodeError:
            logger.warning("Gemini semantic matching failed, falling back to fuzzy matching")
            # Fallback to fuzzy string matching
            return map_profile_to_form_fields(
                profile,
                form_fields,
                country=country,
                app_type=app_type,
            )

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

        return "\n".join(chunks).strip()
    
    def _fuzzy_match_fields(
        self, 
        profile_data: Dict[str, Any], 
        form_field_names: List[str]
    ) -> List[Dict]:
        """Fallback fuzzy string matching"""
        
        mappings = []
        profile_keys = list(profile_data.keys())
        
        for form_field in form_field_names:
            if not form_field:
                continue

            form_field_lower = form_field.lower()

            # High-confidence aliases for vertical document workflows.
            if any(token in form_field_lower for token in ["gst", "vehicle", "deed", "registration", "rc", "document"]):
                mappings.append({
                    "formField": form_field,
                    "profileField": "documentId",
                    "value": str(profile_data.get("documentId", "")),
                    "transformation": "none",
                    "confidence": 0.92,
                })
                continue
            
            best_match = None
            best_score = 0
            best_value = ""
            
            for profile_key in profile_keys:
                score = fuzz.token_set_ratio(form_field.lower(), profile_key.lower())
                
                if score > best_score:
                    best_score = score
                    best_match = profile_key
                    best_value = str(profile_data.get(profile_key, ""))
            
            if best_match and best_score > 60:
                mappings.append({
                    "formField": form_field,
                    "profileField": best_match,
                    "value": best_value,
                    "transformation": "none",
                    "confidence": best_score / 100.0
                })
        
        return mappings
    
    def _get_default_form_fields(self) -> List[Dict]:
        """Default form fields if none provided"""
        return [
            {"name": "fullName"},
            {"name": "firstName"},
            {"name": "lastName"},
            {"name": "dateOfBirth"},
            {"name": "dob"},
            {"name": "gender"},
            {"name": "address"},
            {"name": "city"},
            {"name": "state"},
            {"name": "pincode"},
            {"name": "documentId"},
        ]
