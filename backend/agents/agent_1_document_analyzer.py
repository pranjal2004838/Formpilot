"""Agent 1: Document Analyzer - Extract identity from documents using Gemini Vision"""
import json
import base64
import logging
from typing import Dict, Any
import google.generativeai as genai
from datetime import datetime

from agents.base import Agent, AgentInput, AgentOutput
from models.schemas import IdentityProfile, ExtractedField

logger = logging.getLogger(__name__)


class DocumentAnalyzerAgent(Agent):
    """
    Agent 1: Extract identity from document images using Google Gemini Vision API
    
    Inputs:
        - document_image: base64 encoded image
        - document_type: "aadhaar" | "passport" | "pan"
    
    Outputs:
        - Identity profile with confidence scores per field
        - Overall confidence score
        - Warnings for low-confidence fields
    """
    
    def __init__(self, gemini_api_key: str):
        super().__init__(name="DocumentAnalyzer")
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """Execute document analysis"""
        
        document_image = input_data.metadata.get("document_image")
        document_type = input_data.metadata.get("document_type", "aadhaar")
        
        # Validation
        if not document_image:
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=0,
                errors=["Missing document_image in input"]
            )
        
        try:
            # Decode image from base64
            try:
                image_bytes = base64.b64decode(document_image)
            except Exception as e:
                logger.error(f"Failed to decode image: {str(e)}")
                return AgentOutput(
                    status="error",
                    data={},
                    confidence=0,
                    execution_time_ms=0,
                    errors=[f"Invalid image data: {str(e)}"]
                )
            
            # Extract with Gemini Vision
            profile = await self._extract_with_gemini(image_bytes, document_type)

            profile_dict = {
                "fullName": profile.fullName.dict(),
                "dob": profile.dob.dict(),
                "gender": profile.gender.dict(),
                "address": {k: v.dict() for k, v in profile.address.items()},
                "documentId": profile.documentId.dict(),
                "documentType": profile.documentType,
                "overallConfidence": profile.overallConfidence,
                "warnings": profile.warnings,
                "extracted_at": profile.extracted_at.isoformat()
            }
            
            # Return success
            return AgentOutput(
                status="success",
                data={
                    "profile": profile_dict
                },
                confidence=profile.overallConfidence
            )
        
        except Exception as e:
            logger.error(f"Document extraction failed: {str(e)}", exc_info=True)
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=0,
                errors=[f"Document extraction failed: {str(e)}"]
            )
    
    async def _extract_with_gemini(
        self, 
        image_bytes: bytes, 
        doc_type: str
    ) -> IdentityProfile:
        """Extract identity from document using Gemini Vision API"""
        
        prompt = self._get_extraction_prompt(doc_type)
        
        try:
            # Call Gemini Vision API
            response = self.model.generate_content([
                prompt,
                {"mime_type": "image/jpeg", "data": image_bytes}
            ])
            
            response_text = response.text
            
            # Clean markdown wrapping if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON response
            extracted = json.loads(response_text)
            
            # Build IdentityProfile
            profile = IdentityProfile(
                fullName=ExtractedField(
                    value=extracted.get('fullName', ''),
                    confidence=float(extracted.get('fullName_confidence', 0.90)),
                    source="gemini"
                ),
                dob=ExtractedField(
                    value=extracted.get('dob', ''),
                    confidence=float(extracted.get('dob_confidence', 0.90)),
                    source="gemini"
                ),
                gender=ExtractedField(
                    value=extracted.get('gender', ''),
                    confidence=float(extracted.get('gender_confidence', 0.95)),
                    source="gemini"
                ),
                address={
                    'street': ExtractedField(
                        value=extracted.get('address', {}).get('street', ''),
                        confidence=float(extracted.get('street_confidence', 0.85)),
                        source="gemini"
                    ),
                    'city': ExtractedField(
                        value=extracted.get('address', {}).get('city', ''),
                        confidence=float(extracted.get('city_confidence', 0.90)),
                        source="gemini"
                    ),
                    'state': ExtractedField(
                        value=extracted.get('address', {}).get('state', ''),
                        confidence=float(extracted.get('state_confidence', 0.90)),
                        source="gemini"
                    ),
                    'pincode': ExtractedField(
                        value=extracted.get('address', {}).get('pincode', ''),
                        confidence=float(extracted.get('pincode_confidence', 0.95)),
                        source="gemini"
                    ),
                },
                documentId=ExtractedField(
                    value=extracted.get('documentId', ''),
                    confidence=float(extracted.get('documentId_confidence', 0.95)),
                    source="gemini"
                ),
                documentType=doc_type,
                overallConfidence=float(extracted.get('overall_confidence', 0.90)),
                warnings=extracted.get('warnings', [])
            )
            
            return profile
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response: {response_text}")
            raise Exception(f"Invalid JSON response from Gemini: {str(e)}")
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise
    
    def _get_extraction_prompt(self, doc_type: str) -> str:
        """Get specialized extraction prompt for document type"""
        
        if doc_type == "aadhaar":
            return """
You are an expert at reading Aadhaar cards from India. Extract the following information from this Aadhaar card image:

1. Full Name (exactly as shown on card)
2. Date of Birth (in DD/MM/YYYY format)
3. Gender (Male/Female/Other)
4. Address (street, city, state, pincode)
5. Aadhaar Number (12-digit number)

IMPORTANT: Return ONLY valid JSON with no markdown formatting, no extra text before or after.

Return this exact JSON structure (fill in actual values):
{
    "fullName": "PRANJAL KUMAR SINGH",
    "fullName_confidence": 0.95,
    "dob": "15/05/1998",
    "dob_confidence": 0.92,
    "gender": "Male",
    "gender_confidence": 0.98,
    "address": {
        "street": "123 Main Street",
        "city": "Bangalore",
        "state": "Karnataka",
        "pincode": "560034"
    },
    "street_confidence": 0.88,
    "city_confidence": 0.90,
    "state_confidence": 0.92,
    "pincode_confidence": 0.95,
    "documentId": "123456789012",
    "documentId_confidence": 0.97,
    "overall_confidence": 0.92,
    "warnings": []
}

If any field is not visible or unclear, set confidence to 0.5 or lower and add to warnings array.
"""
        
        elif doc_type == "passport":
            return """
You are an expert at reading passports. Extract identity information from this passport image:

1. Full Name
2. Date of Birth (DD/MM/YYYY)
3. Gender
4. Nationality
5. Passport Number
6. Address (if visible)

Return ONLY valid JSON with no markdown:
{
    "fullName": "...",
    "fullName_confidence": 0.95,
    "dob": "...",
    "dob_confidence": 0.90,
    "gender": "...",
    "gender_confidence": 0.95,
    "address": {
        "street": "...",
        "city": "...",
        "state": "...",
        "pincode": "..."
    },
    "street_confidence": 0.80,
    "city_confidence": 0.85,
    "state_confidence": 0.85,
    "pincode_confidence": 0.80,
    "documentId": "...",
    "documentId_confidence": 0.98,
    "overall_confidence": 0.90,
    "warnings": []
}
"""
        
        else:
            return """
Extract all visible personal identity information from this document.

Return JSON with:
- fullName
- dob (DD/MM/YYYY)
- gender
- address (street, city, state, pincode)
- documentId

Include confidence scores for each field (0-1).
Return ONLY valid JSON with no markdown formatting.
"""
