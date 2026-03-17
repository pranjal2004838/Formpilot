"""Unit tests for deterministic compliance rule engine."""

from compliance.rule_engine import evaluate_compliance


def _profile(document_id: str, document_type: str = "gst_registration"):
    return {
        "fullName": {"value": "Acme Trading LLP", "confidence": 0.94, "source": "test"},
        "dob": {"value": "15/05/1990", "confidence": 0.9, "source": "test"},
        "gender": {"value": "Male", "confidence": 0.9, "source": "test"},
        "address": {
            "street": {"value": "1 Residency Road", "confidence": 0.9, "source": "test"},
            "city": {"value": "Bangalore", "confidence": 0.9, "source": "test"},
            "state": {"value": "Karnataka", "confidence": 0.9, "source": "test"},
            "pincode": {"value": "560001", "confidence": 0.9, "source": "test"},
        },
        "documentId": {"value": document_id, "confidence": 0.97, "source": "test"},
        "documentType": document_type,
    }


def test_gst_registration_compliance_passes_for_valid_gstin():
    result = evaluate_compliance(
        profile=_profile("29ABCDE1234F1Z5", "gst_registration"),
        country="IN",
        app_type="gst_registration",
    )

    assert result["eligible"] is True
    assert result["complianceScore"] >= 80
    assert any(check["check"] == "gstin_format_validation" and check["passed"] for check in result["validationResults"])


def test_gst_registration_compliance_fails_for_invalid_gstin():
    result = evaluate_compliance(
        profile=_profile("29ABCDE1234F1Z", "gst_registration"),
        country="IN",
        app_type="gst_registration",
    )

    assert result["eligible"] is False
    assert any(check["check"] == "gstin_format_validation" and not check["passed"] for check in result["validationResults"])
    assert result["riskLevel"] in {"medium", "high"}
