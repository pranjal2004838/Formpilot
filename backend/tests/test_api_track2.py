"""API-level tests for Track 2 readiness paths."""

import time

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_and_judge_readiness_endpoints():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    readiness = client.get("/api/judge/readiness")
    assert readiness.status_code == 200
    payload = readiness.json()
    assert payload["score"] >= 90
    assert isinstance(payload["checks"], list)
    assert any(c["name"] == "Persistent workflow history" for c in payload["checks"])

    compliance = client.get("/api/compliance/dashboard")
    assert compliance.status_code == 200
    compliance_payload = compliance.json()
    assert "summary" in compliance_payload
    assert "top_violations" in compliance_payload

    case_study = client.get("/api/compliance/case-study?sample_size=50")
    assert case_study.status_code == 200
    case_payload = case_study.json()
    assert case_payload["summary"]["sample_size"] == 50
    assert "by_document_type" in case_payload

    docs = client.get("/api/supported-documents")
    assert docs.status_code == 200
    doc_types = {d["type"] for d in docs.json()["document_types"]}
    assert {"vehicle_registration", "property_deed", "gst_registration"}.issubset(doc_types)


def test_simulated_workflow_end_to_end_with_audit_and_history():
    # 1x1 PNG base64 payload
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
            "form_title": "Judge E2E Test",
            "form_fields": [],
            "notify_slack": False,
            "upload_sharepoint": False,
            "hitl_enabled": True,
        },
    )
    assert start.status_code == 200
    wf = start.json()
    workflow_id = wf["workflow_id"]
    assert wf["mode"] in {"simulated", "real"}

    # Poll until terminal
    terminal = None
    for _ in range(40):
        status = client.get(f"/api/workflows/{workflow_id}/status")
        assert status.status_code == 200
        state = status.json()
        terminal = state["status"]
        if terminal in {"completed", "failed", "rejected"}:
            break
        time.sleep(0.2)

    assert terminal == "completed"

    result = client.get(f"/api/workflows/{workflow_id}/result")
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "completed"
    assert body.get("pdf_base64")

    audit = client.get(f"/api/workflows/{workflow_id}/audit")
    assert audit.status_code == 200
    events = audit.json()["events"]
    assert len(events) >= 2

    history = client.get("/api/workflows")
    assert history.status_code == 200
    ids = {item["workflow_id"] for item in history.json()["workflows"]}
    assert workflow_id in ids
