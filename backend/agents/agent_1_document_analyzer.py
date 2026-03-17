"""Agent 1: Document Analyzer - Extract identity from documents using Gemini Vision"""
import json
import base64
import logging
from typing import Dict, Any
from google import genai
from google.genai import types
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
        self.client = genai.Client(api_key=gemini_api_key)
        self.model_name = "gemini-2.0-flash"
    
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
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type=self._detect_mime_type(image_bytes)),
                ],
            )

            response_text = self._response_text(response)
            
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

    @staticmethod
    def _detect_mime_type(image_bytes: bytes) -> str:
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_bytes.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"
    
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

        elif doc_type == "vehicle_registration":
            return """
You are an expert at reading Indian vehicle registration certificates (RC).

Extract:
1. Full Name of registered owner
2. Date of Birth (if present, DD/MM/YYYY)
3. Gender (if present)
4. Address (street, city, state, pincode)
5. Vehicle registration number as documentId (example: KA01AB1234)

Return ONLY valid JSON with this shape:
{
    "fullName": "...",
    "fullName_confidence": 0.92,
    "dob": "...",
    "dob_confidence": 0.75,
    "gender": "...",
    "gender_confidence": 0.70,
    "address": {
        "street": "...",
        "city": "...",
        "state": "...",
        "pincode": "..."
    },
    "street_confidence": 0.82,
    "city_confidence": 0.88,
    "state_confidence": 0.90,
    "pincode_confidence": 0.90,
    "documentId": "KA01AB1234",
    "documentId_confidence": 0.97,
    "overall_confidence": 0.90,
    "warnings": []
}
"""

        elif doc_type == "property_deed":
            return """
You are an expert at reading Indian property deed documents.

Extract:
1. Full Name (primary owner)
2. Date of Birth (if present, DD/MM/YYYY)
3. Gender (if present)
4. Property address (street, city, state, pincode)
5. Deed reference number as documentId (format similar to STATE-DEED-YYYY-NNNN)

Return ONLY valid JSON with this shape:
{
    "fullName": "...",
    "fullName_confidence": 0.90,
    "dob": "...",
    "dob_confidence": 0.70,
    "gender": "...",
    "gender_confidence": 0.65,
    "address": {
        "street": "...",
        "city": "...",
        "state": "...",
        "pincode": "..."
    },
    "street_confidence": 0.90,
    "city_confidence": 0.90,
    "state_confidence": 0.90,
    "pincode_confidence": 0.88,
    "documentId": "KA-DEED-2024-0451",
    "documentId_confidence": 0.93,
    "overall_confidence": 0.88,
    "warnings": []
}
"""

        elif doc_type == "gst_registration":
            return """
You are an expert at reading Indian GST registration certificates.

Extract:
1. Legal business name into fullName
2. Date of registration (if present) into dob field in DD/MM/YYYY format
3. Business constitution / gender-like marker into gender if available else empty string
4. Registered business address (street, city, state, pincode)
5. GSTIN as documentId

Return ONLY valid JSON with this shape:
{
    "fullName": "...",
    "fullName_confidence": 0.92,
    "dob": "...",
    "dob_confidence": 0.65,
    "gender": "...",
    "gender_confidence": 0.55,
    "address": {
        "street": "...",
        "city": "...",
        "state": "...",
        "pincode": "..."
    },
    "street_confidence": 0.88,
    "city_confidence": 0.89,
    "state_confidence": 0.92,
    "pincode_confidence": 0.90,
    "documentId": "29ABCDE1234F1Z5",
    "documentId_confidence": 0.97,
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
