"""Shared heuristics for mapping extracted profile data to form fields."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from fuzzywuzzy import fuzz


COUNTRY_NAMES = {
    "IN": ("India", "Indian"),
    "US": ("United States", "American"),
    "UK": ("United Kingdom", "British"),
    "CA": ("Canada", "Canadian"),
}


FIELD_ALIASES = {
    "fullName": [
        "full name",
        "applicant name",
        "name of applicant",
        "citizen name",
        "name",
    ],
    "firstName": ["first name", "given name", "forename"],
    "lastName": ["last name", "surname", "family name"],
    "dateOfBirth": ["date of birth", "birth date", "dob", "dateofbirth"],
    "gender": ["gender", "sex"],
    "address": ["address", "street address", "address line", "street", "addr"],
    "city": ["city", "district", "town", "locality"],
    "state": ["state", "province", "region", "state province"],
    "pincode": ["pincode", "pin code", "postal code", "zip code", "postcode"],
    "country": ["country", "country code"],
    "nationality": ["nationality", "citizenship"],
    "documentId": [
        "document id",
        "id number",
        "reference number",
        "application number",
        "aadhaar",
        "aadhar",
        "passport number",
        "pan number",
        "gstin",
        "registration number",
        "vehicle number",
        "deed number",
    ],
    "documentType": ["document type", "application type", "service", "service type"],
    "keyword": ["keyword", "search", "search term", "query", "kw"],
    "vehicleNumber": ["vehicle number", "registration number", "vehicle registration number", "rc number"],
    "propertyDeedId": ["property deed", "deed id", "deed reference", "property reference"],
    "gstin": ["gstin", "gst number", "gst registration"],
}


def normalize_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _extract_value(field: Any) -> str:
    if isinstance(field, dict):
        return str(field.get("value") or "")
    return str(field or "")


def flatten_profile(
    profile: Dict[str, Any],
    *,
    country: str = "",
    app_type: str = "",
) -> Dict[str, str]:
    full_name = _extract_value(profile.get("fullName"))
    dob = _extract_value(profile.get("dob"))
    gender = _extract_value(profile.get("gender"))
    address = profile.get("address") if isinstance(profile.get("address"), dict) else {}
    street = _extract_value(address.get("street"))
    city = _extract_value(address.get("city"))
    state = _extract_value(address.get("state"))
    pincode = _extract_value(address.get("pincode"))
    document_id = _extract_value(profile.get("documentId"))
    document_type = str(profile.get("documentType") or "")

    name_parts = [part for part in full_name.split() if part]
    first_name = name_parts[0] if name_parts else ""
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    country_code = str(country or "").upper()
    country_name, nationality = COUNTRY_NAMES.get(country_code, (country_code, country_code))
    keyword = app_type or document_type or full_name

    values = {
        "fullName": full_name,
        "firstName": first_name,
        "lastName": last_name,
        "dateOfBirth": dob,
        "dob": dob,
        "gender": gender,
        "address": street,
        "street": street,
        "city": city,
        "district": city,
        "state": state,
        "pincode": pincode,
        "postalCode": pincode,
        "country": country_name,
        "nationality": nationality,
        "documentId": document_id,
        "documentType": document_type,
        "keyword": keyword,
        "searchTerm": keyword,
        "vehicleNumber": document_id if document_type == "vehicle_registration" else "",
        "propertyDeedId": document_id if document_type == "property_deed" else "",
        "gstin": document_id if document_type == "gst_registration" else "",
        "aadhaarNumber": document_id if document_type == "aadhaar" else "",
        "passportNumber": document_id if document_type == "passport" else "",
        "panNumber": document_id if document_type == "pan" else "",
    }
    return {key: value for key, value in values.items() if value}


def _field_descriptor(field: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("name", "id", "label", "placeholder", "ariaLabel", "type"):
        value = field.get(key)
        if value:
            parts.append(str(value))
    for option in field.get("options", []) or []:
        option_label = option.get("label") or option.get("text") or option.get("value")
        if option_label:
            parts.append(str(option_label))
    return " ".join(parts)


def _best_profile_field(field: Dict[str, Any], profile_values: Dict[str, str]) -> Tuple[str, str, str, float]:
    field_name = str(field.get("name") or field.get("id") or field.get("label") or "")
    field_text = normalize_text(_field_descriptor(field))
    field_name_norm = normalize_text(field_name)

    if field_name_norm in {"kw", "keyword", "search", "query"} or "search" in field_text:
        value = profile_values.get("keyword") or profile_values.get("documentType") or profile_values.get("fullName")
        if value:
            return "documentType", value, "none", 0.95

    if any(token in field_text for token in ("first name", "given name", "forename")):
        value = profile_values.get("firstName")
        if value:
            return "fullName", value, "split", 0.95

    if any(token in field_text for token in ("last name", "surname", "family name")):
        value = profile_values.get("lastName")
        if value:
            return "fullName", value, "split", 0.95

    best_key = ""
    best_score = 0
    for profile_key, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            score = fuzz.token_set_ratio(field_text, normalize_text(alias))
            if field_name_norm == normalize_text(alias):
                score = max(score, 100)
            if field_name_norm == normalize_text(profile_key):
                score = max(score, 100)
            if score > best_score:
                best_key = profile_key
                best_score = score

    if not best_key or best_score < 60:
        return "", "", "none", 0.0

    profile_field = best_key
    if best_key == "dateOfBirth":
        profile_field = "dob"
    if best_key == "keyword":
        profile_field = "documentType"

    value = profile_values.get(best_key)
    if not value and best_key == "dateOfBirth":
        value = profile_values.get("dob", "")
    if not value:
        return "", "", "none", 0.0

    confidence = min(max(best_score / 100.0, 0.65), 0.98)
    return profile_field, value, "none", confidence


def map_profile_to_form_fields(
    profile: Dict[str, Any],
    form_fields: List[Dict[str, Any]],
    *,
    country: str = "",
    app_type: str = "",
) -> List[Dict[str, Any]]:
    profile_values = flatten_profile(profile, country=country, app_type=app_type)
    mappings: List[Dict[str, Any]] = []

    for field in form_fields or []:
        field_name = str(field.get("name") or field.get("id") or field.get("label") or "").strip()
        if not field_name:
            continue

        profile_field, value, transformation, confidence = _best_profile_field(field, profile_values)
        if not profile_field or not value:
            continue

        mappings.append(
            {
                "formField": field_name,
                "profileField": profile_field,
                "value": value,
                "transformation": transformation,
                "confidence": confidence,
            }
        )

    return mappings