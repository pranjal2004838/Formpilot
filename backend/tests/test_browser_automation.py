"""Tests for browser automation mapping and workflow integration."""

import asyncio
import time

from fastapi.testclient import TestClient

import main
from agents.base import AgentOutput
from utils.form_mapping import map_profile_to_form_fields


client = TestClient(main.app)


def test_map_profile_to_live_portal_fields(sample_identity_profile):
    fields = [
        {"name": "kw", "label": "Search", "type": "text"},
        {"name": "state_id", "label": "State", "type": "select"},
    ]

    mappings = map_profile_to_form_fields(
        sample_identity_profile,
        fields,
        country="IN",
        app_type="passport",
    )
    by_field = {item["formField"]: item for item in mappings}

    assert by_field["kw"]["value"] == "passport"
    assert by_field["state_id"]["value"] == "NY"


def test_simulated_workflow_with_browser_automation(monkeypatch):
    async def fake_discover_form_fields(target_url, *, headless=True, timeout_ms=30000):
        return {
            "target_url": target_url,
            "resolved_url": target_url,
            "fields": [
                {"name": "kw", "label": "Search", "type": "text"},
                {"name": "state_id", "label": "State", "type": "select"},
            ],
            "policy": {"submit_allowed": True},
            "blockers": [],
        }

    async def fake_run(input_data):
        return AgentOutput(
            status="success",
            data={
                "target_url": input_data.metadata["browser_automation"]["target_url"],
                "resolved_url": "https://services.india.gov.in/service/search?kw=passport",
                "submitted": True,
                "message": "Submitted via Search.",
                "policy": {"submit_allowed": True},
                "blockers": [],
                "matched_fields": [{"formField": "kw", "control": "kw", "value": "passport"}],
                "skipped_fields": [],
                "screenshots": [],
            },
            confidence=0.95,
        )

    monkeypatch.setattr(main.browser_submitter, "discover_form_fields", fake_discover_form_fields)
    monkeypatch.setattr(main.browser_submitter, "run", fake_run)

    doc_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

    start = client.post(
        "/api/workflows/start",
        json={
            "document_image": doc_b64,
            "document_type": "passport",
            "country": "IN",
            "app_type": "passport",
            "form_fields": [],
            "notify_slack": False,
            "upload_sharepoint": False,
            "hitl_enabled": True,
            "browser_automation": {
                "target_url": "https://services.india.gov.in/service/search",
                "submit": True,
                "headless": True,
            },
        },
    )
    assert start.status_code == 200
    workflow_id = start.json()["workflow_id"]

    terminal = None
    for _ in range(40):
        status = client.get(f"/api/workflows/{workflow_id}/status")
        assert status.status_code == 200
        terminal = status.json()["status"]
        if terminal in {"completed", "failed", "rejected"}:
            break
        time.sleep(0.2)

    assert terminal == "completed"

    result = client.get(f"/api/workflows/{workflow_id}/result")
    assert result.status_code == 200
    payload = result.json()
    assert payload["browser_submission"]["submitted"] is True
    assert payload["portal_fields"][0]["name"] == "kw"


def test_browser_hitl_captcha_interaction(monkeypatch):
    """Test that CAPTCHA detection triggers HITL mode instead of blocking."""
    
    async def fake_run_with_captcha(input_data):
        """Simulate browser agent detecting CAPTCHA and returning HITL state."""
        return AgentOutput(
            status="awaiting_user_interaction",
            data={
                "target_url": "https://example.com/form",
                "resolved_url": "https://example.com/form",
                "submitted": False,
                "needs_human_interaction": True,
                "interaction_type": "solve_captcha",
                "interaction_prompt": (
                    "🔒 CAPTCHA detected: The form requires you to solve a CAPTCHA challenge. "
                    "Please solve it in the browser window, and we'll resume submission once you confirm."
                ),
                "interaction_session_id": "test-session-123",
                "paused_at": "2026-03-18T10:00:00",
                "matched_fields": 2,
                "skipped_fields": 1,
                "filled_values": {"name": "John Doe", "email": "john@example.com"},
                "blockers_detected": ["CAPTCHA detected on target page."],
                "screenshots": ["before.png", "after_fill.png"],
                "policy": {"submit_allowed": False},
            },
            confidence=0.85,
        )
    
    async def fake_discover_form_fields(target_url, *, headless=True, timeout_ms=30000):
        return {
            "target_url": target_url,
            "resolved_url": target_url,
            "fields": [
                {"name": "name", "label": "Name", "type": "text"},
                {"name": "email", "label": "Email", "type": "email"},
                {"name": "captcha", "label": "CAPTCHA", "type": "text"},
            ],
            "policy": {"submit_allowed": False},
            "blockers": ["CAPTCHA detected on target page."],
        }

    monkeypatch.setattr(main.browser_submitter, "run", fake_run_with_captcha)
    monkeypatch.setattr(main.browser_submitter, "discover_form_fields", fake_discover_form_fields)

    doc_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

    # Start workflow with CAPTCHA-protected form
    start = client.post(
        "/api/workflows/start",
        json={
            "document_image": doc_b64,
            "document_type": "passport",
            "country": "IN",
            "app_type": "passport",
            "form_fields": [],
            "notify_slack": False,
            "upload_sharepoint": False,
            "hitl_enabled": True,
            "browser_automation": {
                "target_url": "https://example.com/form",
                "submit": True,
                "allow_hitl": True,
            },
        },
    )
    assert start.status_code == 200
    workflow_id = start.json()["workflow_id"]

    # Poll until HITL is triggered
    for _ in range(50):
        status = client.get(f"/api/workflows/{workflow_id}/status")
        assert status.status_code == 200
        if status.json()["status"] == "awaiting_user_interaction":
            break
        time.sleep(0.1)

    # Verify HITL state
    status_resp = client.get(f"/api/workflows/{workflow_id}/status")
    assert status_resp.status_code == 200
    state = status_resp.json()
    assert state["status"] == "awaiting_user_interaction"
    assert state.get("current_interaction_type") == "solve_captcha"

    # Get workflow result to verify HITL data
    result = client.get(f"/api/workflows/{workflow_id}/result")
    assert result.status_code == 200
    payload = result.json()
    browser_sub = payload["browser_submission"]
    assert browser_sub["needs_human_interaction"] is True
    assert browser_sub["interaction_type"] == "solve_captcha"
    assert browser_sub["interaction_session_id"] == "test-session-123"
    assert len(browser_sub["filled_values"]) > 0
    assert browser_sub["matched_fields"] == 2

    # Simulate user solving CAPTCHA and resuming
    resume = client.post(
        f"/api/workflows/{workflow_id}/browser-interaction/resume",
        json={"notes": "CAPTCHA solved successfully"},
    )
    if resume.status_code != 200:
        print(f"Resume endpoint error: {resume.status_code}")
        print(f"Response: {resume.json()}")
    assert resume.status_code == 200
    assert "resumed" in resume.json()["status"]

    # Poll until workflow completes
    for _ in range(50):
        status = client.get(f"/api/workflows/{workflow_id}/status")
        assert status.status_code == 200
        if status.json()["status"] in {"completed", "failed"}:
            break
        time.sleep(0.1)

    # Final verification
    final_status = client.get(f"/api/workflows/{workflow_id}/status")
    assert final_status.json()["status"] in {"completed", "running"}



def test_browser_hitl_otp_interaction(monkeypatch):
    """Test that OTP detection triggers HITL mode."""
    
    async def fake_run_with_otp(input_data):
        """Simulate browser agent detecting OTP and returning HITL state."""
        return AgentOutput(
            status="awaiting_user_interaction",
            data={
                "target_url": "https://example.com/secure-form",
                "resolved_url": "https://example.com/secure-form",
                "submitted": False,
                "needs_human_interaction": True,
                "interaction_type": "enter_otp",
                "interaction_prompt": (
                    "📱 OTP Authentication required: The form expects a One-Time Password or Multi-Factor Authentication. "
                    "Please complete the OTP verification in the browser, and we'll resume submission when ready."
                ),
                "interaction_session_id": "test-otp-456",
                "paused_at": "2026-03-18T10:05:00",
                "matched_fields": 3,
                "skipped_fields": 0,
                "filled_values": {
                    "name": "Jane Smith",
                    "email": "jane@example.com",
                    "phone": "9876543210",
                },
                "blockers_detected": ["Authentication or OTP flow detected on target page."],
                "screenshots": ["before.png", "after_fill.png"],
                "policy": {"submit_allowed": False},
            },
            confidence=0.90,
        )
    
    async def fake_discover_form_fields(target_url, *, headless=True, timeout_ms=30000):
        return {
            "target_url": target_url,
            "resolved_url": target_url,
            "fields": [
                {"name": "name", "label": "Name", "type": "text"},
                {"name": "email", "label": "Email", "type": "email"},
                {"name": "phone", "label": "Phone", "type": "tel"},
            ],
            "policy": {"submit_allowed": False},
            "blockers": ["Authentication or OTP flow detected on target page."],
        }

    monkeypatch.setattr(main.browser_submitter, "run", fake_run_with_otp)
    monkeypatch.setattr(main.browser_submitter, "discover_form_fields", fake_discover_form_fields)

    doc_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

    # Start workflow with OTP-protected form  
    start = client.post(
        "/api/workflows/start",
        json={
            "document_image": doc_b64,
            "document_type": "passport",
            "country": "IN",
            "app_type": "passport",
            "form_fields": [],
            "notify_slack": False,
            "upload_sharepoint": False,
            "hitl_enabled": True,
            "browser_automation": {
                "target_url": "https://example.com/secure-form",
                "submit": True,
                "allow_hitl": True,
            },
        },
    )
    assert start.status_code == 200
    workflow_id = start.json()["workflow_id"]

    # Poll until HITL is triggered
    for _ in range(50):
        status = client.get(f"/api/workflows/{workflow_id}/status")
        assert status.status_code == 200
        if status.json()["status"] == "awaiting_user_interaction":
            break
        time.sleep(0.1)

    # Verify OTP HITL state
    status_resp = client.get(f"/api/workflows/{workflow_id}/status")
    assert status_resp.status_code == 200
    state = status_resp.json()
    assert state["status"] == "awaiting_user_interaction"
    assert state.get("current_interaction_type") == "enter_otp"

    result = client.get(f"/api/workflows/{workflow_id}/result")
    assert result.status_code == 200
    payload = result.json()
    browser_sub = payload["browser_submission"]
    assert browser_sub["interaction_type"] == "enter_otp"
    assert browser_sub["matched_fields"] == 3
    assert "jane@example.com" in str(browser_sub["filled_values"])