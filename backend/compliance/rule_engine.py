"""Deterministic compliance rule engine for FormPilot vertical workflows."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

SUPPORTED_DOCUMENTS: List[Dict[str, str]] = [
    {"type": "passport", "description": "International Passport"},
    {"type": "aadhaar", "description": "Aadhaar Card (India)"},
    {"type": "pan", "description": "PAN Card (India)"},
    {"type": "driving_license", "description": "Driving Licence"},
    {"type": "vehicle_registration", "description": "Vehicle Registration Certificate (India)"},
    {"type": "property_deed", "description": "Registered Property Deed (India)"},
    {"type": "gst_registration", "description": "GST Registration Certificate (India)"},
    {"type": "generic", "description": "Generic Identity / Compliance Document"},
]

INDIA_STATE_PIN_PREFIXES: Dict[str, List[str]] = {
    "karnataka": ["56", "57", "58"],
    "maharashtra": ["40", "41", "42", "43", "44"],
    "delhi": ["11"],
    "tamil nadu": ["60", "61", "62", "63", "64"],
    "west bengal": ["70", "71", "72", "73", "74"],
    "gujarat": ["36", "37", "38", "39"],
    "uttar pradesh": ["20", "21", "22", "23", "24", "25", "26", "27", "28"],
}

GST_STATE_CODE_TO_NAME: Dict[str, str] = {
    "07": "delhi",
    "09": "uttar pradesh",
    "19": "west bengal",
    "24": "gujarat",
    "27": "maharashtra",
    "29": "karnataka",
    "33": "tamil nadu",
}

INDIA_VEHICLE_STATE_CODES = {
    "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ", "HP",
    "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ",
    "NL", "OD", "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK", "UP", "WB",
}


def evaluate_compliance(
    profile: Dict[str, Any],
    country: str,
    app_type: str,
    document_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate compliance with deterministic, regulation-aware checks."""

    country_code = (country or "IN").upper()
    app_type_norm = (app_type or "generic").strip().lower()
    doc_type_norm = (
        (document_type or _field_value(profile, ["documentType"]) or "generic")
        .strip()
        .lower()
    )

    checks: List[Dict[str, Any]] = []

    def add_check(
        check: str,
        passed: bool,
        requirement: str,
        explanation: str,
        *,
        severity: str = "critical",
        regulation_ref: Optional[str] = None,
    ) -> None:
        entry = {
            "check": check,
            "passed": passed,
            "requirement": requirement,
            "explanation": explanation,
            "severity": severity,
        }
        if regulation_ref:
            entry["regulation_ref"] = regulation_ref
        checks.append(entry)

    full_name = _field_value(profile, ["fullName", "value"]) or ""
    dob_value = _field_value(profile, ["dob", "value"]) or ""
    gender = _field_value(profile, ["gender", "value"]) or ""
    state = _field_value(profile, ["address", "state", "value"]) or ""
    city = _field_value(profile, ["address", "city", "value"]) or ""
    pincode = _field_value(profile, ["address", "pincode", "value"]) or ""
    doc_id = _normalize_id(_field_value(profile, ["documentId", "value"]))

    missing_fields: List[str] = []
    if not full_name.strip():
        missing_fields.append("fullName")
    if not dob_value.strip():
        missing_fields.append("dob")
    if not doc_id:
        missing_fields.append("documentId")

    add_check(
        "core_identity_completeness",
        len(missing_fields) == 0,
        "Name, DOB, and document identifier are required",
        "All mandatory identity fields are present."
        if not missing_fields
        else f"Missing required fields: {', '.join(missing_fields)}",
        regulation_ref="FORMPILOT_CORE_IDENTITY_v1",
    )

    age = _parse_age(dob_value)
    age_ok = age is not None and age >= 18
    add_check(
        "age_requirement",
        age_ok,
        "Applicant must be 18+ years",
        f"Age computed from DOB is {age}."
        if age is not None
        else "DOB could not be parsed for age validation.",
        regulation_ref="GOV_GENERAL_AGE_18PLUS",
    )

    if country_code == "IN":
        _apply_india_rules(
            checks,
            doc_type_norm,
            app_type_norm,
            doc_id,
            state,
            city,
            pincode,
            gender,
        )
    else:
        _apply_global_rules(checks, country_code, app_type_norm, doc_type_norm, doc_id)

    failed_critical = [c for c in checks if (not c["passed"]) and c.get("severity") != "warning"]
    failed_warnings = [c for c in checks if (not c["passed"]) and c.get("severity") == "warning"]
    eligible = len(failed_critical) == 0

    compliance_score = max(0, 100 - (len(failed_critical) * 20) - (len(failed_warnings) * 8))
    if compliance_score < 60 or len(failed_critical) >= 2:
        risk_level = "high"
    elif failed_critical or len(failed_warnings) >= 2:
        risk_level = "medium"
    else:
        risk_level = "low"

    violations = [
        {
            "check": c["check"],
            "requirement": c["requirement"],
            "explanation": c["explanation"],
            "severity": c.get("severity", "critical"),
            "regulation_ref": c.get("regulation_ref"),
        }
        for c in checks
        if not c["passed"]
    ]

    regulation_tags = sorted(
        {
            c["regulation_ref"]
            for c in checks
            if c.get("regulation_ref")
        }
    )

    if eligible:
        notes = (
            f"Compliance checks passed for {country_code}/{app_type_norm}. "
            f"Score: {compliance_score}."
        )
    else:
        failed_names = ", ".join(v["check"] for v in violations)
        notes = (
            f"Compliance issues detected: {failed_names}. "
            f"Score: {compliance_score}."
        )

    return {
        "eligible": eligible,
        "validationResults": checks,
        "missingFields": missing_fields,
        "notes": notes,
        "country": country_code,
        "app_type": app_type_norm,
        "document_type": doc_type_norm,
        "complianceScore": compliance_score,
        "riskLevel": risk_level,
        "violations": violations,
        "regulationTags": regulation_tags,
        "validated_at": datetime.now().isoformat(),
    }


def _apply_india_rules(
    checks: List[Dict[str, Any]],
    doc_type: str,
    app_type: str,
    doc_id: str,
    state: str,
    city: str,
    pincode: str,
    gender: str,
) -> None:
    def add(
        check: str,
        passed: bool,
        requirement: str,
        explanation: str,
        *,
        severity: str = "critical",
        regulation_ref: Optional[str] = None,
    ) -> None:
        entry = {
            "check": check,
            "passed": passed,
            "requirement": requirement,
            "explanation": explanation,
            "severity": severity,
        }
        if regulation_ref:
            entry["regulation_ref"] = regulation_ref
        checks.append(entry)

    residency_passed = bool(state.strip()) and bool(city.strip())
    add(
        "indian_residency_signal",
        residency_passed,
        "Address should include state and city in India",
        "State and city are available for residency validation."
        if residency_passed
        else "Missing state/city needed for Indian residency checks.",
        regulation_ref="INDIA_RESIDENCY_SIGNAL_v1",
    )

    if doc_type == "aadhaar":
        aadhaar_ok = _is_valid_aadhaar(doc_id)
        add(
            "uidai_aadhaar_format_and_checksum",
            aadhaar_ok,
            "Aadhaar must be 12 digits with valid checksum",
            "Aadhaar number passes UIDAI checksum validation."
            if aadhaar_ok
            else "Aadhaar format/checksum is invalid.",
            regulation_ref="UIDAI_AADHAAR_VERHOEFF",
        )

    if doc_type == "pan":
        pan_ok = _is_valid_pan(doc_id)
        add(
            "pan_structure_validation",
            pan_ok,
            "PAN must match AAAAA9999A format",
            "PAN structure is valid." if pan_ok else "PAN format is invalid.",
            regulation_ref="INCOME_TAX_PAN_STRUCTURE",
        )

    gst_context = doc_type == "gst_registration" or "gst" in app_type
    if gst_context:
        gst_ok = _is_valid_gstin(doc_id)
        add(
            "gstin_format_validation",
            gst_ok,
            "GSTIN must be 15 chars in legal format",
            "GSTIN format is valid." if gst_ok else "GSTIN format is invalid.",
            regulation_ref="GST_ACT_2017_GSTIN_FORMAT",
        )
        if gst_ok and state:
            gst_state_name = GST_STATE_CODE_TO_NAME.get(doc_id[:2], "")
            state_match = gst_state_name and _state_matches(gst_state_name, state)
            add(
                "gst_state_code_consistency",
                bool(state_match),
                "GST state code must align with declared state",
                "GST state code aligns with profile state."
                if state_match
                else "GST state code does not match declared address state.",
                severity="warning",
                regulation_ref="GST_STATE_CODE_ALIGNMENT",
            )

    vehicle_context = doc_type == "vehicle_registration" or app_type == "vehicle_registration"
    if vehicle_context:
        vehicle_ok = _is_valid_vehicle_number(doc_id)
        add(
            "vehicle_registration_format",
            vehicle_ok,
            "Vehicle number must follow Indian RTO format",
            "Vehicle registration number matches RTO format."
            if vehicle_ok
            else "Vehicle number format does not match standard RTO registration pattern.",
            regulation_ref="MV_ACT_RTO_NUMBERING",
        )
        if vehicle_ok:
            state_code = doc_id[:2]
            add(
                "vehicle_state_code_valid",
                state_code in INDIA_VEHICLE_STATE_CODES,
                "Vehicle state code should be a valid Indian state/UT prefix",
                f"Detected vehicle state code {state_code}."
                if state_code in INDIA_VEHICLE_STATE_CODES
                else f"Unknown vehicle state code {state_code}.",
                severity="warning",
                regulation_ref="MV_ACT_STATE_CODE",
            )

    property_context = doc_type == "property_deed" or "property" in app_type
    if property_context:
        deed_ok = _is_valid_property_deed_id(doc_id)
        add(
            "property_deed_reference_format",
            deed_ok,
            "Property deed reference should follow STATE-DEED-YYYY-NNNN pattern",
            "Property deed number has compliant structure."
            if deed_ok
            else "Property deed reference format is invalid.",
            regulation_ref="INDIA_REGISTRATION_ACT_DEED_REF",
        )

    state_norm = _normalize_text(state)
    pincode_norm = _digits_only(pincode)
    if state_norm and pincode_norm and len(pincode_norm) == 6:
        expected = INDIA_STATE_PIN_PREFIXES.get(state_norm)
        if expected:
            state_pin_ok = any(pincode_norm.startswith(prefix) for prefix in expected)
            add(
                "state_pincode_consistency",
                state_pin_ok,
                "Pincode prefix should align with declared state",
                "Pincode prefix aligns with state mapping."
                if state_pin_ok
                else f"Pincode {pincode_norm} does not align with state {state}.",
                severity="warning",
                regulation_ref="INDIA_POST_PIN_STATE_MAPPING",
            )

    if gender:
        add(
            "gender_field_present",
            True,
            "Gender should be present for KYC completeness",
            "Gender field is available for downstream government forms.",
            severity="warning",
            regulation_ref="KYC_FIELD_COMPLETENESS",
        )


def _apply_global_rules(
    checks: List[Dict[str, Any]],
    country_code: str,
    app_type: str,
    doc_type: str,
    doc_id: str,
) -> None:
    def add(
        check: str,
        passed: bool,
        requirement: str,
        explanation: str,
        *,
        severity: str = "critical",
        regulation_ref: Optional[str] = None,
    ) -> None:
        entry = {
            "check": check,
            "passed": passed,
            "requirement": requirement,
            "explanation": explanation,
            "severity": severity,
        }
        if regulation_ref:
            entry["regulation_ref"] = regulation_ref
        checks.append(entry)

    add(
        "document_identifier_present",
        bool(doc_id),
        "A valid document identifier is required",
        "Document ID is present." if doc_id else "Document ID is missing.",
        regulation_ref="GLOBAL_ID_PRESENCE_v1",
    )

    visa_context = app_type == "visa"
    if visa_context:
        passport_like = doc_type in {"passport", "generic"}
        add(
            "visa_requires_passport",
            passport_like,
            "Visa applications require passport identity proof",
            "Accepted passport-class document was supplied."
            if passport_like
            else f"Document type {doc_type} is not accepted for visa workflows.",
            regulation_ref=f"{country_code}_VISA_BASE_DOC_RULE",
        )


def _field_value(payload: Any, path: List[str]) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _normalize_id(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value).strip().upper())


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _digits_only(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _parse_age(dob_value: str) -> Optional[int]:
    if not dob_value:
        return None

    formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"]
    dob_date: Optional[date] = None
    for fmt in formats:
        try:
            dob_date = datetime.strptime(dob_value.strip(), fmt).date()
            break
        except ValueError:
            continue

    if dob_date is None:
        return None

    today = date.today()
    return today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))


def _is_valid_pan(pan: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan or ""))


def _is_valid_gstin(gstin: str) -> bool:
    if not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", gstin or ""):
        return False
    return _is_valid_pan(gstin[2:12])


def _is_valid_vehicle_number(vehicle_id: str) -> bool:
    normalized = re.sub(r"[^A-Z0-9]", "", vehicle_id or "")
    return bool(re.fullmatch(r"[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}", normalized))


def _is_valid_property_deed_id(deed_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{2}-DEED-[0-9]{4}-[0-9]{4,}", deed_id or ""))


def _state_matches(lhs: str, rhs: str) -> bool:
    lhs_norm = _normalize_text(lhs)
    rhs_norm = _normalize_text(rhs)
    return lhs_norm == rhs_norm or lhs_norm in rhs_norm or rhs_norm in lhs_norm


# Verhoeff checksum tables used by UIDAI Aadhaar validation.
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def _is_valid_aadhaar(aadhaar: str) -> bool:
    number = _digits_only(aadhaar)
    if len(number) != 12:
        return False

    checksum = 0
    reverse_digits = list(map(int, reversed(number)))
    for idx, digit in enumerate(reverse_digits):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[idx % 8][digit]]
    return checksum == 0
