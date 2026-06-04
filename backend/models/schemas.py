"""Data models and schemas for FormPilot"""
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from datetime import datetime
import uuid


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
    warnings: List[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=datetime.now)


class ValidationResult(BaseModel):
    """Eligibility validation result"""
    eligible: bool
    validationResults: List[Dict] = Field(default_factory=list)
    missingFields: List[str] = Field(default_factory=list)
    notes: str
    validated_at: datetime = Field(default_factory=datetime.now)


class FormMapping(BaseModel):
    """Individual form field mapping"""
    formFieldName: str
    extractedFieldName: str
    value: str
    transformation: str  # "none" | "format_conversion" | "split" | "join"
    confidence: float


class BrowserSubmissionResult(BaseModel):
    """Browser automation submission result with HITL support"""
    submitted: bool
    resolved_url: Optional[str] = None
    matched_fields: int = 0
    skipped_fields: int = 0
    screenshots: List[str] = Field(default_factory=list)
    submit_allowed: bool = False
    
    # Human-In-The-Loop (HITL) fields
    needs_human_interaction: bool = False
    interaction_type: Optional[str] = None  # "solve_captcha" | "enter_otp" | "solve_password_gate" | "other"
    interaction_prompt: Optional[str] = None  # Human-readable prompt
    interaction_session_id: Optional[str] = None  # UUID to track pause/resume
    paused_at: Optional[datetime] = None
    filled_values: Optional[Dict[str, str]] = None  # Auto-saved field values before pause
    form_snapshot: Optional[Dict] = None  # Form state when paused
    blockers_detected: List[str] = Field(default_factory=list)  # List of blocker reasons
    
    # Metadata
    policy_reasons: List[str] = Field(default_factory=list)
    government_domain: bool = False
    method: str = "unknown"  # "get" | "post"


class WorkflowOutput(BaseModel):
    """Complete workflow output"""
    workflow_id: str
    status: str  # "in_progress" | "completed" | "failed" | "rejected" | "cancelled" | "awaiting_user_interaction"
    profile: Optional[Dict] = None
    validation: Optional[Dict] = None
    mappings: Optional[List[Dict]] = None
    portal_fields: Optional[List[Dict]] = None
    browser_submission: Optional[BrowserSubmissionResult] = None
    pdf_url: Optional[str] = None
    pdf_base64: Optional[str] = None
    pdf_file_name: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    completed_at: Optional[datetime] = None

class CompanyAccount(BaseModel):
    """Enterprise company account"""
    account_id: str
    name: str
    created_at: datetime

class EmployeeProfile(BaseModel):
    """Grouped employee entity containing multiple documents"""
    profile_id: str
    account_id: str
    full_name: str
    dob: Optional[str] = None
    status: str = "incomplete"
    created_at: datetime
    documents: List[Dict] = Field(default_factory=list)

class BulkUploadResponse(BaseModel):
    """Response for a bulk upload operation"""
    account_id: str
    processed_files: int
    profiles_created: int
    profiles: List[EmployeeProfile]
    message: str
