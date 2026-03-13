"""Pytest configuration and fixtures"""
import pytest
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Ensure backend package is importable in tests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Ensure asyncio event loop is available for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_identity_profile() -> Dict[str, Any]:
    """Sample extracted identity profile for testing"""
    return {
        "fullName": {
            "value": "John Doe",
            "confidence": 0.95,
            "source": "gemini"
        },
        "dob": {
            "value": "1990-01-15",
            "confidence": 0.90,
            "source": "gemini"
        },
        "gender": {
            "value": "Male",
            "confidence": 0.98,
            "source": "gemini"
        },
        "address": {
            "street": {
                "value": "123 Main St",
                "confidence": 0.85,
                "source": "gemini"
            },
            "city": {
                "value": "New York",
                "confidence": 0.92,
                "source": "gemini"
            },
            "state": {
                "value": "NY",
                "confidence": 0.90,
                "source": "gemini"
            },
            "pincode": {
                "value": "10001",
                "confidence": 0.88,
                "source": "gemini"
            }
        },
        "documentId": {
            "value": "A123456789",
            "confidence": 0.93,
            "source": "gemini"
        },
        "documentType": "passport",
        "overallConfidence": 0.91,
        "warnings": [],
        "extracted_at": "2024-03-13T10:00:00Z"
    }


@pytest.fixture
def sample_validation_result() -> Dict[str, Any]:
    """Sample validation result for testing"""
    return {
        "eligible": True,
        "validationResults": [
            {"check": "Age Check", "passed": True, "message": "Age >= 18"},
            {"check": "Passport Validity", "passed": True, "message": "Passport valid for next 6 months"},
            {"check": "Country Eligibility", "passed": True, "message": "Country is eligible for visa"}
        ],
        "missingFields": [],
        "notes": "All eligibility checks passed",
        "validated_at": "2024-03-13T10:00:30Z"
    }


@pytest.fixture
def sample_field_mappings() -> list:
    """Sample field mappings for testing"""
    return [
        {
            "formField": "fullName",
            "profileField": "fullName",
            "value": "John Doe",
            "transformation": "none",
            "confidence": 0.95
        },
        {
            "formField": "firstName",
            "profileField": "fullName",
            "value": "John",
            "transformation": "split",
            "confidence": 0.95
        },
        {
            "formField": "lastName",
            "profileField": "fullName",
            "value": "Doe",
            "transformation": "split",
            "confidence": 0.95
        },
        {
            "formField": "dateOfBirth",
            "profileField": "dob",
            "value": "1990-01-15",
            "transformation": "none",
            "confidence": 0.90
        },
        {
            "formField": "gender",
            "profileField": "gender",
            "value": "Male",
            "transformation": "none",
            "confidence": 0.98
        },
        {
            "formField": "address",
            "profileField": "address.street",
            "value": "123 Main St",
            "transformation": "none",
            "confidence": 0.85
        },
        {
            "formField": "city",
            "profileField": "address.city",
            "value": "New York",
            "transformation": "none",
            "confidence": 0.92
        },
        {
            "formField": "state",
            "profileField": "address.state",
            "value": "NY",
            "transformation": "none",
            "confidence": 0.90
        },
        {
            "formField": "pincode",
            "profileField": "address.pincode",
            "value": "10001",
            "transformation": "none",
            "confidence": 0.88
        }
    ]


@pytest.fixture
def sample_workflow_input() -> Dict[str, Any]:
    """Sample workflow input for testing"""
    return {
        "document_image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "document_type": "passport",
        "form_fields": [
            {"name": "fullName", "label": "Full Name", "required": True},
            {"name": "firstName", "label": "First Name", "required": True},
            {"name": "lastName", "label": "Last Name", "required": True},
            {"name": "dateOfBirth", "label": "Date of Birth", "required": True},
        ],
        "country": "IN",
        "app_type": "visa",
        "form_title": "Visa Application Form"
    }


@pytest.fixture
def sample_form_fields() -> list:
    """Sample form field definitions"""
    return [
        {"name": "fullName", "label": "Full Name", "type": "text", "required": True},
        {"name": "firstName", "label": "First Name", "type": "text", "required": True},
        {"name": "lastName", "label": "Last Name", "type": "text", "required": True},
        {"name": "dateOfBirth", "label": "Date of Birth", "type": "date", "required": True},
        {"name": "gender", "label": "Gender", "type": "select", "required": True},
        {"name": "address", "label": "Street Address", "type": "text", "required": True},
        {"name": "city", "label": "City", "type": "text", "required": True},
        {"name": "state", "label": "State", "type": "text", "required": True},
        {"name": "pincode", "label": "Postal Code", "type": "text", "required": True},
    ]


@pytest.fixture
def test_data_json() -> Dict[str, Any]:
    """Comprehensive test data"""
    return {
        "profiles": [
            {
                "id": "test_1",
                "fullName": "Alice Smith",
                "dob": "1985-05-20",
                "country": "US"
            },
            {
                "id": "test_2",
                "fullName": "Bob Jones",
                "dob": "1992-08-10",
                "country": "IN"
            }
        ],
        "documents": [
            {"type": "passport", "country": "US"},
            {"type": "aadhaar", "country": "IN"}
        ]
    }
