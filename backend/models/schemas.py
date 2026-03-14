"""Data models and schemas for FormPilot"""
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from datetime import datetime


class ExtractedField(BaseModel):
    """Individual extracted field with confidence"""
    value: str
    confidence: float = Field(ge=0, le=1)
    source: str  # "gemini" | "claude" | "consensus" | "missing"


class AddressModel(BaseModel):
    """Address components"""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None


class IdentityProfile(BaseModel):
    """Extracted identity information"""
    fullName: ExtractedField
    dob: ExtractedField
    gender: ExtractedField
    address: Dict[str, ExtractedField]
    documentId: ExtractedField
    documentType: str
    overallConfidence: float
    warnings: List[str] = []
    extracted_at: datetime = Field(default_factory=datetime.now)


class ValidationResult(BaseModel):
    """Eligibility validation result"""
    eligible: bool
    validationResults: List[Dict] = []
    missingFields: List[str] = []
    notes: str
    validated_at: datetime = Field(default_factory=datetime.now)


class FormMapping(BaseModel):
    """Individual form field mapping"""
    formFieldName: str
    extractedFieldName: str
    value: str
    transformation: str  # "none" | "format_conversion" | "split" | "join"
    confidence: float


class WorkflowOutput(BaseModel):
    """Complete workflow output"""
    workflow_id: str
    status: str  # "in_progress" | "completed" | "failed" | "cancelled"
    profile: Optional[Dict] = None
    validation: Optional[Dict] = None
    mappings: Optional[List[Dict]] = None
    pdf_url: Optional[str] = None
    pdf_base64: Optional[str] = None
    pdf_file_name: Optional[str] = None
    errors: List[str] = []
    message: Optional[str] = None
    completed_at: Optional[datetime] = None
