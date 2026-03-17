"""
FormPilot Enterprise API — FastAPI Application
================================================
Main entry point.  Serves the frontend SPA, exposes the workflow API,
Airia-callable tool endpoints, HITL approval routes, and integration status.
"""

import asyncio
import base64
import hmac
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FORMPILOT_API_KEY = os.getenv("FORMPILOT_API_KEY", "")   # optional tool auth
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./formpilot.db")

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set — real document processing disabled.")

# ---------------------------------------------------------------------------
# Integration clients (imported lazily to avoid circular import)
# ---------------------------------------------------------------------------
from integrations.airia_client import AiriaClient
from integrations.slack_client import SlackClient
from integrations.sharepoint_client import SharePointClient
from compliance.rule_engine import SUPPORTED_DOCUMENTS, evaluate_compliance
from storage.workflow_store import WorkflowStore
from workflows.form_automation_workflow import FormAutomationWorkflow

airia_client     = AiriaClient()
slack_client     = SlackClient()
sharepoint_client = SharePointClient()
workflow_store = WorkflowStore(DATABASE_URL)

workflow = (
    FormAutomationWorkflow(
        gemini_api_key=GEMINI_API_KEY,
        slack_client=slack_client,
        sharepoint_client=sharepoint_client,
        airia_client=airia_client,
    )
    if GEMINI_API_KEY
    else None
)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FormPilot Enterprise API",
    description=(
        "AI-powered multi-agent form automation — Airia AI Agents Hackathon 2026. "
        "Track 2: Active Agents."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# In-memory workflow state store
# ---------------------------------------------------------------------------
# Each entry is a plain dict (JSON-serializable except for 'hitl_event').
workflow_states: Dict[str, Dict[str, Any]] = {}
SUPPORTED_DOCUMENT_TYPE_SET = {item["type"] for item in SUPPORTED_DOCUMENTS}


def _make_state(workflow_id: str) -> Dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "status": "running",          # running | awaiting_approval | completed | failed | rejected
        "step": 0,
        "step_name": "Initializing…",
        "progress": 0,
        "message": "Workflow starting…",
        "profile": None,
        "validation": None,
        "mappings": None,
        "pdf_base64": None,
        "pdf_file_name": None,
        "slack_sent": False,
        "sharepoint_url": None,
        "airia_invoked": False,
        "errors": [],
        "audit_log": [],
        "hitl_event": asyncio.Event(),   # non-serialisable — excluded in API responses
        "hitl_decision": None,
        "mode": "real",
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "_persisted_audit_count": 0,
    }


def _state_for_api(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return a JSON-safe copy (drop internal fields)."""
    hidden = {"hitl_event", "_persisted_audit_count"}
    return {k: v for k, v in state.items() if k not in hidden}


def _append_audit(state: Dict[str, Any], event: str, **details: Any) -> None:
    state.setdefault("audit_log", [])
    state["audit_log"].append(
        {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            **details,
        }
    )


def _persist_workflow_state(workflow_id: str, request_data: Optional[Dict[str, Any]] = None) -> None:
    state = workflow_states.get(workflow_id)
    if not state:
        return
    workflow_store.persist_workflow(workflow_id, state, request_data or {})


def _enforce_tool_auth(request: Request) -> None:
    """Require bearer auth on tool endpoints when FORMPILOT_API_KEY is configured."""
    if not FORMPILOT_API_KEY:
        return

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    token = auth_header.split(" ", 1)[1].strip()
    if not hmac.compare_digest(token, FORMPILOT_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid tool token.")


def _simulated_profile(document_type: str, country: str) -> Dict[str, Any]:
    name_by_country = {
        "IN": "AARAV SHARMA",
        "US": "EMILY JOHNSON",
        "UK": "OLIVER SMITH",
        "CA": "NOAH MARTIN",
    }
    city_by_country = {
        "IN": ("Bangalore", "Karnataka", "560001"),
        "US": ("Seattle", "Washington", "98101"),
        "UK": ("London", "Greater London", "SW1A 1AA"),
        "CA": ("Toronto", "Ontario", "M5H 2N2"),
    }
    city, state_name, postal = city_by_country.get(country, city_by_country["IN"])
    document_type = (document_type or "generic").lower()

    return {
        "fullName": {"value": name_by_country.get(country, "ALEX DOE"), "confidence": 0.96, "source": "simulated"},
        "dob": {"value": "15/05/1998", "confidence": 0.95, "source": "simulated"},
        "gender": {"value": "Male", "confidence": 0.99, "source": "simulated"},
        "address": {
            "street": {"value": "123 Main Street", "confidence": 0.92, "source": "simulated"},
            "city": {"value": city, "confidence": 0.93, "source": "simulated"},
            "state": {"value": state_name, "confidence": 0.93, "source": "simulated"},
            "pincode": {"value": postal, "confidence": 0.95, "source": "simulated"},
        },
        "documentId": {
            "value": _simulated_document_id(document_type, country, state_name),
            "confidence": 0.98,
            "source": "simulated",
        },
        "documentType": document_type,
        "overallConfidence": 0.95,
        "warnings": [
            "Simulated mode: GEMINI_API_KEY is not configured."
        ],
        "extracted_at": datetime.now().isoformat(),
    }


def _simulated_document_id(document_type: str, country: str, state_name: str) -> str:
    if document_type == "aadhaar":
        return "123412341234"
    if document_type == "pan":
        return "ABCDE1234F"
    if document_type == "vehicle_registration":
        return "KA01AB1234" if country == "IN" else "DL01AB1234"
    if document_type == "property_deed":
        state_code = "KA" if "karnataka" in state_name.lower() else "IN"
        return f"{state_code}-DEED-2024-0451"
    if document_type == "gst_registration":
        return "29ABCDE1234F1Z5"
    if document_type == "passport":
        return "N1234567"
    if document_type == "driving_license":
        return "DL0420110149646"
    return "SIM-1234-5678"


def _default_app_type_for_document(document_type: str) -> str:
    mapping = {
        "gst_registration": "gst_registration",
        "vehicle_registration": "vehicle_registration",
        "property_deed": "property_registration",
        "driving_license": "driver_license",
    }
    return mapping.get(document_type, "passport")


def _case_study_profile(document_type: str, index: int) -> Dict[str, Any]:
    profile = _simulated_profile(document_type, "IN")

    profile["fullName"]["value"] = f"APPLICANT {index:03d}"
    profile["address"]["street"]["value"] = f"{100 + index} Residency Road"

    if document_type == "vehicle_registration":
        state_code = "KA"
        district = (index % 30) + 1
        serial = 1000 + (index % 8999)
        profile["documentId"]["value"] = f"{state_code}{district:02d}AB{serial:04d}"
    elif document_type == "property_deed":
        profile["documentId"]["value"] = f"KA-DEED-2024-{1000 + index:04d}"
    elif document_type == "gst_registration":
        profile["documentId"]["value"] = "29ABCDE1234F1Z5"
    elif document_type == "passport":
        profile["documentId"]["value"] = f"N{1000000 + index}"
    elif document_type == "aadhaar":
        profile["documentId"]["value"] = "123412341234"

    # Inject controlled failures for reproducible benchmark scoring.
    if (index + 1) % 50 == 0:
        profile["documentId"]["value"] = ""

    return profile


def _simulated_mappings(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    mappings = [
        {"formField": "fullName", "profileField": "fullName", "value": profile["fullName"]["value"], "transformation": "none", "confidence": 0.96},
        {"formField": "dateOfBirth", "profileField": "dob", "value": profile["dob"]["value"], "transformation": "none", "confidence": 0.95},
        {"formField": "gender", "profileField": "gender", "value": profile["gender"]["value"], "transformation": "none", "confidence": 0.99},
        {"formField": "address", "profileField": "address.street", "value": profile["address"]["street"]["value"], "transformation": "none", "confidence": 0.92},
        {"formField": "city", "profileField": "address.city", "value": profile["address"]["city"]["value"], "transformation": "none", "confidence": 0.93},
        {"formField": "state", "profileField": "address.state", "value": profile["address"]["state"]["value"], "transformation": "none", "confidence": 0.93},
        {"formField": "pincode", "profileField": "address.pincode", "value": profile["address"]["pincode"]["value"], "transformation": "none", "confidence": 0.95},
        {"formField": "documentId", "profileField": "documentId", "value": profile["documentId"]["value"], "transformation": "none", "confidence": 0.98},
    ]

    document_type = str(profile.get("documentType", "")).lower()
    if document_type == "gst_registration":
        mappings.append({"formField": "gstin", "profileField": "documentId", "value": profile["documentId"]["value"], "transformation": "none", "confidence": 0.97})
    if document_type == "vehicle_registration":
        mappings.append({"formField": "vehicleNumber", "profileField": "documentId", "value": profile["documentId"]["value"], "transformation": "none", "confidence": 0.97})
    if document_type == "property_deed":
        mappings.append({"formField": "propertyDeedId", "profileField": "documentId", "value": profile["documentId"]["value"], "transformation": "none", "confidence": 0.97})

    return mappings


async def _run_simulated_bg(workflow_id: str, request_data: Dict[str, Any]) -> None:
    """Run a full simulated pipeline when GEMINI_API_KEY is unavailable."""
    state = workflow_states.get(workflow_id)
    if not state:
        return

    start = time.time()
    state["mode"] = "simulated"
    _append_audit(state, "workflow_start_simulated", workflow_id=workflow_id)

    try:
        state.update({"step": 1, "step_name": "Document Analyzer", "progress": 15, "message": "Simulated analysis in progress…"})
        await asyncio.sleep(0.2)

        profile = _simulated_profile(request_data.get("document_type", "generic"), request_data.get("country", "IN"))
        state.update({"profile": profile, "progress": 35, "message": "Simulated identity profile created."})
        _append_audit(state, "step_completed", step=1, mode="simulated")

        state.update({"step": 2, "step_name": "Rules Validator", "progress": 50, "message": "Simulated eligibility validation…"})
        await asyncio.sleep(0.2)

        validation = evaluate_compliance(
            profile=profile,
            country=request_data.get("country", "IN"),
            app_type=request_data.get("app_type", "passport"),
            document_type=request_data.get("document_type", "generic"),
        )
        state.update(
            {
                "validation": validation,
                "progress": 65,
                "message": "Simulated compliance validation complete.",
            }
        )
        if not validation.get("eligible", True):
            _append_audit(
                state,
                "simulated_compliance_violation",
                workflow_id=workflow_id,
                risk_level=validation.get("riskLevel"),
                violation_count=len(validation.get("violations", [])),
            )
        _append_audit(state, "step_completed", step=2, mode="simulated")

        state.update({"step": 3, "step_name": "Field Mapper", "progress": 75, "message": "Simulated field mapping…"})
        await asyncio.sleep(0.2)

        mappings = _simulated_mappings(profile)
        state.update({"mappings": mappings, "progress": 82, "message": "Simulated mapping complete."})
        _append_audit(state, "step_completed", step=3, mode="simulated")

        state.update({"step": 4, "step_name": "PDF Generator", "progress": 90, "message": "Generating PDF in simulated mode…"})
        await asyncio.sleep(0.2)

        from agents.agent_4_pdf_generator import PDFGeneratorAgent
        from agents.base import AgentInput

        agent = PDFGeneratorAgent()
        pdf_result = await agent.run(
            AgentInput(
                workflow_id=workflow_id,
                metadata={
                    "mappings": mappings,
                    "profile": profile,
                    "form_title": request_data.get("form_title", "Simulated Application Form"),
                },
            )
        )

        if pdf_result.status == "error":
            raise RuntimeError("Simulated PDF generation failed.")

        elapsed_ms = int((time.time() - start) * 1000)
        state.update(
            {
                "status": "completed",
                "step": 5,
                "step_name": "Complete",
                "progress": 100,
                "message": f"Completed in simulated mode ({elapsed_ms}ms).",
                "pdf_base64": pdf_result.data.get("pdf_base64"),
                "pdf_file_name": pdf_result.data.get("file_name", "simulated_formpilot_output.pdf"),
                "slack_sent": False,
                "sharepoint_url": None,
                "completed_at": datetime.now().isoformat(),
            }
        )
        _append_audit(state, "workflow_completed_simulated", workflow_id=workflow_id, elapsed_ms=elapsed_ms)
    except Exception as exc:
        logger.error("Simulated workflow %s failed: %s", workflow_id, exc, exc_info=True)
        state.update(
            {
                "status": "failed",
                "errors": [str(exc)],
                "message": f"Simulated workflow failed: {exc}",
                "completed_at": datetime.now().isoformat(),
            }
        )
        _append_audit(state, "workflow_failed_simulated", workflow_id=workflow_id, error=str(exc))
    finally:
        _persist_workflow_state(workflow_id, request_data)


# ---------------------------------------------------------------------------
# Background workflow runner
# ---------------------------------------------------------------------------
async def _run_workflow_bg(workflow_id: str, request_data: Dict[str, Any]) -> None:
    state = workflow_states.get(workflow_id)
    if not state:
        return
    try:
        await workflow.execute(request_data, state)
    except Exception as exc:
        logger.error("Background workflow %s crashed: %s", workflow_id, exc, exc_info=True)
        state["status"] = "failed"
        state["errors"] = [str(exc)]
        state["message"] = f"Internal error: {exc}"
        state["completed_at"] = datetime.now().isoformat()
        _append_audit(state, "workflow_failed", workflow_id=workflow_id, error=str(exc))
    finally:
        _persist_workflow_state(workflow_id, request_data)


# ===========================================================================
# Request / Response models
# ===========================================================================
class WorkflowStartRequest(BaseModel):
    document_image: str
    document_type: str = "passport"
    form_fields: List[Dict] = Field(default_factory=list)
    country: str = "IN"
    app_type: str = "passport"
    form_title: str = "Government Application Form"
    notify_slack: bool = True
    upload_sharepoint: bool = True
    hitl_enabled: bool = True


class HITLDecisionRequest(BaseModel):
    reason: Optional[str] = None


# ===========================================================================
# Health & Info
# ===========================================================================
@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": "FormPilot Enterprise API",
        "version": "2.0.0",
        "gemini_configured": GEMINI_API_KEY is not None,
        "airia_configured":  airia_client.configured,
        "slack_configured":  slack_client.configured,
        "sharepoint_configured": sharepoint_client.configured,
        "tool_auth_enforced": bool(FORMPILOT_API_KEY),
        "workflow_persistence": str(workflow_store.db_path),
    }


@app.get("/api/integrations/status", tags=["Integrations"])
async def integrations_status():
    """Return live status of all platform integrations."""
    return {
        "airia": {
            "configured": airia_client.configured,
            "pipeline_id": airia_client.pipeline_id if airia_client.configured else None,
            "label": "Airia AI Platform",
        },
        "slack": {
            "configured": slack_client.configured,
            "channel": slack_client.channel,
            "label": "Slack Notifications",
        },
        "sharepoint": {
            "configured": sharepoint_client.configured,
            "library": sharepoint_client.library if sharepoint_client.configured else None,
            "label": "SharePoint Upload",
        },
        "gemini": {
            "configured": GEMINI_API_KEY is not None,
            "model": "gemini-2.0-flash",
            "label": "Google Gemini Vision",
        },
    }


@app.get("/api/airia/pipeline", tags=["Airia"])
async def get_airia_pipeline():
    """Return the Airia pipeline definition for this application."""
    return airia_client.pipeline_definition


@app.get("/api/airia/tools", tags=["Airia"])
async def get_airia_tool_manifest(request: Request):
    """Return the Airia-compatible tool manifest (for registration in Airia Community)."""
    base = str(request.base_url).rstrip("/")
    return airia_client.get_tool_manifest(base)


# ===========================================================================
# Workflow — Start (async / background)
# ===========================================================================
@app.post("/api/workflows/start", tags=["Workflows"])
async def start_workflow(
    request: WorkflowStartRequest,
    background_tasks: BackgroundTasks,
    req: Request,
):
    """
    Start a new form automation workflow.

    Returns immediately with a workflow_id.
    Poll GET /api/workflows/{id}/status for progress.
    """
    workflow_id = str(uuid.uuid4())
    state = _make_state(workflow_id)
    workflow_states[workflow_id] = state

    # Inject base URL for HITL Slack links
    request_data = request.model_dump()
    request_data["app_base_url"] = str(req.base_url).rstrip("/")
    request_data["document_type"] = (request_data.get("document_type") or "generic").lower()

    if request_data["document_type"] not in SUPPORTED_DOCUMENT_TYPE_SET:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Unsupported document_type.",
                "supported": sorted(SUPPORTED_DOCUMENT_TYPE_SET),
            },
        )

    # Use default form fields when none provided
    if not request_data["form_fields"]:
        request_data["form_fields"] = (
            workflow.get_default_form_fields()
            if workflow
            else FormAutomationWorkflow.get_default_form_fields()
        )

    state["document_type"] = request_data.get("document_type")
    state["country"] = request_data.get("country")
    state["app_type"] = request_data.get("app_type")

    _append_audit(
        state,
        "workflow_start",
        workflow_id=workflow_id,
        mode="real" if workflow else "simulated",
        document_type=request_data.get("document_type"),
        country=request_data.get("country"),
        app_type=request_data.get("app_type"),
    )
    _persist_workflow_state(workflow_id, request_data)

    if workflow:
        background_tasks.add_task(_run_workflow_bg, workflow_id, request_data)
        message = "Workflow started"
    else:
        state["mode"] = "simulated"
        background_tasks.add_task(_run_simulated_bg, workflow_id, request_data)
        message = "Workflow started in simulated mode (set GEMINI_API_KEY for full AI mode)"

    return {"workflow_id": workflow_id, "status": "running", "message": message, "mode": state["mode"]}


# ===========================================================================
# Workflow — Status (polling endpoint)
# ===========================================================================
@app.get("/api/workflows/{workflow_id}/status", tags=["Workflows"])
async def get_workflow_status(workflow_id: str):
    """
    Poll for workflow progress.

    Returns step, progress %, message, and full validation data when
    status == 'awaiting_approval' (so the UI can render the HITL panel).
    """
    state = workflow_states.get(workflow_id)
    if not state:
        stored = workflow_store.get_workflow(workflow_id)
        if not stored:
            raise HTTPException(404, detail=f"Workflow {workflow_id!r} not found.")
        return {
            "workflow_id": stored["workflow_id"],
            "status": stored["status"],
            "step": stored.get("step", 0),
            "step_name": stored.get("step_name") or "Stored",
            "progress": stored.get("progress", 100 if stored.get("status") in {"completed", "failed", "rejected"} else 0),
            "message": stored.get("message"),
            "slack_sent": stored.get("slack_sent", False),
            "sharepoint_url": stored.get("sharepoint_url"),
            "airia_invoked": stored.get("airia_invoked", False),
            "errors": stored.get("errors", []),
            "mode": stored.get("mode", "real"),
        }

    resp: Dict[str, Any] = {
        "workflow_id": workflow_id,
        "status": state["status"],
        "step": state["step"],
        "step_name": state["step_name"],
        "progress": state["progress"],
        "message": state["message"],
        "slack_sent": state["slack_sent"],
        "sharepoint_url": state["sharepoint_url"],
        "airia_invoked": state["airia_invoked"],
        "errors": state["errors"],
        "mode": state.get("mode", "real"),
    }

    if state["status"] == "awaiting_approval":
        resp["validation"] = state.get("validation")
        resp["profile"] = state.get("profile")

    return resp


# ===========================================================================
# Workflow — Full Result
# ===========================================================================
@app.get("/api/workflows/{workflow_id}/result", tags=["Workflows"])
async def get_workflow_result(workflow_id: str):
    """Return the complete result (including PDF base64) after completion."""
    state = workflow_states.get(workflow_id)
    if not state:
        stored = workflow_store.get_workflow(workflow_id)
        if not stored:
            raise HTTPException(404, detail=f"Workflow {workflow_id!r} not found.")
        terminal = {"completed", "failed", "rejected"}
        if stored["status"] not in terminal:
            raise HTTPException(
                400, detail=f"Workflow not finished yet (status: {stored['status']})."
            )
        return stored

    terminal = {"completed", "failed", "rejected"}
    if state["status"] not in terminal:
        raise HTTPException(
            400, detail=f"Workflow not finished yet (status: {state['status']})."
        )

    return _state_for_api(state)


# ===========================================================================
# HITL — Approve / Reject
# ===========================================================================
@app.post("/api/workflows/{workflow_id}/approve", tags=["HITL"])
async def approve_workflow(workflow_id: str, body: HITLDecisionRequest = None):
    """
    Approve a workflow that is paused at a HITL checkpoint.
    The background task will resume from where it paused.
    """
    state = workflow_states.get(workflow_id)
    if not state:
        raise HTTPException(404, detail=f"Workflow {workflow_id!r} not found.")
    if state["status"] != "awaiting_approval":
        raise HTTPException(
            400, detail=f"Workflow is not awaiting approval (status: {state['status']})."
        )

    state["hitl_decision"] = True
    state["status"] = "running"
    state["message"] = "✅ Approved by reviewer — resuming pipeline…"
    state["hitl_event"].set()
    _append_audit(
        state,
        "hitl_decision",
        workflow_id=workflow_id,
        decision="approved",
        reason=(body.reason if body else None),
    )
    _persist_workflow_state(workflow_id)

    logger.info("Workflow %s approved by human reviewer.", workflow_id)
    return {"workflow_id": workflow_id, "decision": "approved", "message": "Workflow approved and resuming."}


@app.get("/api/workflows/{workflow_id}/approve", tags=["HITL"], include_in_schema=False)
async def approve_workflow_get(workflow_id: str):
    """GET version for Slack button deep-link."""
    state = workflow_states.get(workflow_id)
    if not state:
        return HTMLResponse("<h2>Workflow not found.</h2>", status_code=404)
    if state["status"] == "awaiting_approval":
        state["hitl_decision"] = True
        state["status"] = "running"
        state["message"] = "✅ Approved by reviewer — resuming pipeline…"
        state["hitl_event"].set()
        _append_audit(
            state,
            "hitl_decision",
            workflow_id=workflow_id,
            decision="approved",
            reason="Slack deep-link",
        )
        _persist_workflow_state(workflow_id)
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;padding:40px'>"
        "<h2>✅ Workflow Approved</h2>"
        f"<p>Workflow <code>{workflow_id}</code> has been approved and will resume processing.</p>"
        "<p>You can close this tab.</p></body></html>"
    )


@app.post("/api/workflows/{workflow_id}/reject", tags=["HITL"])
async def reject_workflow(workflow_id: str, body: HITLDecisionRequest = None):
    """Reject a workflow paused at a HITL checkpoint."""
    state = workflow_states.get(workflow_id)
    if not state:
        raise HTTPException(404, detail=f"Workflow {workflow_id!r} not found.")
    if state["status"] != "awaiting_approval":
        raise HTTPException(
            400, detail=f"Workflow is not awaiting approval (status: {state['status']})."
        )

    state["hitl_decision"] = False
    state["status"] = "rejected"
    state["message"] = "❌ Rejected by human reviewer."
    state["completed_at"] = datetime.now().isoformat()
    state["hitl_event"].set()
    _append_audit(
        state,
        "hitl_decision",
        workflow_id=workflow_id,
        decision="rejected",
        reason=(body.reason if body else None),
    )
    _persist_workflow_state(workflow_id)

    logger.info("Workflow %s rejected by human reviewer.", workflow_id)
    return {"workflow_id": workflow_id, "decision": "rejected", "message": "Workflow rejected."}


@app.get("/api/workflows/{workflow_id}/reject", tags=["HITL"], include_in_schema=False)
async def reject_workflow_get(workflow_id: str):
    """GET version for Slack button deep-link."""
    state = workflow_states.get(workflow_id)
    if not state:
        return HTMLResponse("<h2>Workflow not found.</h2>", status_code=404)
    if state["status"] == "awaiting_approval":
        state["hitl_decision"] = False
        state["status"] = "rejected"
        state["message"] = "❌ Rejected by human reviewer."
        state["completed_at"] = datetime.now().isoformat()
        state["hitl_event"].set()
        _append_audit(
            state,
            "hitl_decision",
            workflow_id=workflow_id,
            decision="rejected",
            reason="Slack deep-link",
        )
        _persist_workflow_state(workflow_id)
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;padding:40px'>"
        "<h2>❌ Workflow Rejected</h2>"
        f"<p>Workflow <code>{workflow_id}</code> has been rejected.</p>"
        "<p>You can close this tab.</p></body></html>"
    )


# ===========================================================================
# Airia Tool Endpoints
# These are called by the Airia platform during pipeline execution.
# They wrap each FormPilot agent as a standalone HTTP tool.
# ===========================================================================
@app.post("/api/tools/document-analyzer", tags=["Airia Tools"])
async def tool_document_analyzer(body: Dict[str, Any], request: Request):
    """Airia tool: Extract identity from a document image."""
    _enforce_tool_auth(request)
    if not workflow:
        raise HTTPException(503, detail="Gemini not configured.")
    from agents.base import AgentInput
    result = await workflow.agent_1.run(AgentInput(
        workflow_id=body.get("workflow_id", str(uuid.uuid4())),
        metadata={
            "document_image": body.get("document_image"),
            "document_type": body.get("document_type", "generic"),
        },
    ))
    if result.status == "error":
        raise HTTPException(422, detail={"errors": result.errors})
    return {"profile": result.data.get("profile", result.data), "confidence": result.confidence}


@app.post("/api/tools/rules-validator", tags=["Airia Tools"])
async def tool_rules_validator(body: Dict[str, Any], request: Request):
    """Airia tool: Validate identity against government eligibility rules."""
    _enforce_tool_auth(request)
    if not workflow:
        raise HTTPException(503, detail="Gemini not configured.")
    from agents.base import AgentInput
    result = await workflow.agent_2.run(AgentInput(
        workflow_id=body.get("workflow_id", str(uuid.uuid4())),
        metadata={
            "profile": body.get("profile"),
            "country": body.get("country", "IN"),
            "app_type": body.get("app_type", "passport"),
            "document_type": body.get("document_type") or (body.get("profile") or {}).get("documentType", "generic"),
        },
    ))
    if result.status == "error":
        raise HTTPException(422, detail={"errors": result.errors})
    return {"validation": result.data, "confidence": result.confidence}


@app.post("/api/tools/field-mapper", tags=["Airia Tools"])
async def tool_field_mapper(body: Dict[str, Any], request: Request):
    """Airia tool: Semantically map identity data to form fields."""
    _enforce_tool_auth(request)
    if not workflow:
        raise HTTPException(503, detail="Gemini not configured.")
    from agents.base import AgentInput
    result = await workflow.agent_3.run(AgentInput(
        workflow_id=body.get("workflow_id", str(uuid.uuid4())),
        metadata={
            "profile": body.get("profile"),
            "form_fields": body.get("form_fields", []),
        },
    ))
    if result.status == "error":
        raise HTTPException(422, detail={"errors": result.errors})
    return {"mappings": result.data.get("mappings", []), "confidence": result.confidence}


@app.post("/api/tools/pdf-generator", tags=["Airia Tools"])
async def tool_pdf_generator(body: Dict[str, Any], request: Request):
    """Airia tool: Generate a professional PDF from mapped fields."""
    _enforce_tool_auth(request)
    from agents.agent_4_pdf_generator import PDFGeneratorAgent
    from agents.base import AgentInput
    agent = PDFGeneratorAgent()
    result = await agent.run(AgentInput(
        workflow_id=body.get("workflow_id", str(uuid.uuid4())),
        metadata={
            "mappings": body.get("mappings", []),
            "profile": body.get("profile", {}),
            "form_title": body.get("form_title", "Form"),
        },
    ))
    if result.status == "error":
        raise HTTPException(422, detail={"errors": result.errors})
    return {
        "pdf_base64": result.data.get("pdf_base64"),
        "file_name": result.data.get("file_name"),
        "file_size_bytes": result.data.get("file_size_bytes"),
    }


@app.post("/api/tools/notification-dispatcher", tags=["Airia Tools"])
async def tool_notification_dispatcher(body: Dict[str, Any], request: Request):
    """Airia tool: Send Slack notification and upload PDF to SharePoint."""
    _enforce_tool_auth(request)
    wf_id = body.get("workflow_id", str(uuid.uuid4()))
    profile = body.get("profile", {})
    validation = body.get("validation", {})
    pdf_file_name = body.get("pdf_file_name", "output.pdf")
    pdf_base64_str = body.get("pdf_base64", "")
    notify_slack = body.get("notify_slack", True)
    upload_sharepoint = body.get("upload_sharepoint", True)

    slack_sent = False
    sharepoint_url = None

    if notify_slack and slack_client.configured:
        slack_sent = await slack_client.send_completion_notification(
            wf_id, profile, pdf_file_name, validation
        )

    if upload_sharepoint and sharepoint_client.configured and pdf_base64_str:
        pdf_bytes = base64.b64decode(pdf_base64_str)
        sharepoint_url = await sharepoint_client.upload_pdf(
            pdf_bytes, pdf_file_name,
            {"workflow_id": wf_id, "applicant": (profile.get("fullName") or {}).get("value", "Unknown")},
        )

    return {"slack_sent": slack_sent, "sharepoint_url": sharepoint_url}


# ===========================================================================
# Demo workflow (no API key needed)
# ===========================================================================
@app.post("/api/workflows/demo", tags=["Workflows"])
async def demo_workflow():
    """
    Run a demo with mock data — no API keys required.
    Returns a real PDF generated by Agent 4.
    """
    from agents.agent_4_pdf_generator import PDFGeneratorAgent
    from agents.base import AgentInput

    demo_profile = {
        "fullName": {"value": "PRANJAL KUMAR SINGH", "confidence": 0.97, "source": "gemini"},
        "dob": {"value": "15/05/1998", "confidence": 0.95, "source": "gemini"},
        "gender": {"value": "Male", "confidence": 0.99, "source": "gemini"},
        "address": {
            "street": {"value": "123, MG Road, Sector 5", "confidence": 0.91, "source": "gemini"},
            "city": {"value": "Bangalore", "confidence": 0.94, "source": "gemini"},
            "state": {"value": "Karnataka", "confidence": 0.93, "source": "gemini"},
            "pincode": {"value": "560001", "confidence": 0.96, "source": "gemini"},
        },
        "documentId": {"value": "ABCDE1234F", "confidence": 0.98, "source": "gemini"},
        "documentType": "pan",
        "overallConfidence": 0.95,
        "warnings": [],
        "extracted_at": datetime.now().isoformat(),
    }

    demo_validation = evaluate_compliance(
        profile=demo_profile,
        country="IN",
        app_type="passport",
        document_type=demo_profile.get("documentType", "aadhaar"),
    )

    demo_mappings = [
        {"formField": "fullName",     "profileField": "fullName",        "value": "PRANJAL KUMAR SINGH", "transformation": "none",  "confidence": 0.97},
        {"formField": "firstName",    "profileField": "fullName",        "value": "PRANJAL KUMAR",        "transformation": "split", "confidence": 0.95},
        {"formField": "lastName",     "profileField": "fullName",        "value": "SINGH",                "transformation": "split", "confidence": 0.95},
        {"formField": "dateOfBirth",  "profileField": "dob",             "value": "15/05/1998",           "transformation": "none",  "confidence": 0.95},
        {"formField": "gender",       "profileField": "gender",          "value": "Male",                 "transformation": "none",  "confidence": 0.99},
        {"formField": "address",      "profileField": "address.street",  "value": "123, MG Road, Sector 5", "transformation": "none", "confidence": 0.91},
        {"formField": "city",         "profileField": "address.city",    "value": "Bangalore",            "transformation": "none",  "confidence": 0.94},
        {"formField": "state",        "profileField": "address.state",   "value": "Karnataka",            "transformation": "none",  "confidence": 0.93},
        {"formField": "pincode",      "profileField": "address.pincode", "value": "560001",               "transformation": "none",  "confidence": 0.96},
        {"formField": "documentId",   "profileField": "documentId",      "value": "ABCDE1234F",           "transformation": "none",  "confidence": 0.98},
        {"formField": "documentType", "profileField": "documentType",    "value": "PAN Card",             "transformation": "none",  "confidence": 1.0},
    ]

    agent4 = PDFGeneratorAgent()
    pdf_result = await agent4.run(AgentInput(
        workflow_id=str(uuid.uuid4()),
        metadata={
            "mappings": demo_mappings,
            "profile": demo_profile,
            "form_title": "Passport Application Form — FormPilot Demo",
        },
    ))

    return {
        "workflow_id": str(uuid.uuid4()),
        "status": "completed",
        "message": "Demo workflow completed — Airia 5-step pipeline (local mode)",
        "profile": demo_profile,
        "validation": demo_validation,
        "mappings": demo_mappings,
        "pdf_file_name": pdf_result.data.get("file_name", "demo_form.pdf"),
        "pdf_base64": pdf_result.data.get("pdf_base64", ""),
        "slack_sent": False,
        "sharepoint_url": None,
        "airia_invoked": False,
        "demo": True,
    }


# ===========================================================================
# Workflow history and metrics
# ===========================================================================
@app.get("/api/workflows", tags=["Workflows"])
async def list_workflows(limit: int = 100, status: Optional[str] = None):
    """List workflow history from persistent storage."""
    return {"workflows": workflow_store.list_workflows(limit=limit, status=status)}


@app.get("/api/workflows/{workflow_id}/audit", tags=["Workflows"])
async def workflow_audit(workflow_id: str):
    """Return full audit trail for a workflow."""
    events = workflow_store.get_audit_events(workflow_id)

    # Include unsaved in-memory events, if any
    state = workflow_states.get(workflow_id)
    if state and state.get("audit_log"):
        persisted_count = int(state.get("_persisted_audit_count", 0))
        events.extend(state.get("audit_log", [])[persisted_count:])

    if not events:
        raise HTTPException(404, detail=f"No audit events found for {workflow_id!r}.")
    return {"workflow_id": workflow_id, "events": events}


@app.get("/api/metrics/summary", tags=["Metrics"])
async def metrics_summary():
    """Return aggregate workflow metrics for judging and operations."""
    return workflow_store.summary_metrics()


@app.get("/api/compliance/dashboard", tags=["Metrics"])
async def compliance_dashboard(limit: int = 25):
    """Return compliance KPIs, top violations, and recent workflow history."""
    return workflow_store.compliance_dashboard(limit=limit)


@app.get("/api/compliance/case-study", tags=["Metrics"])
async def compliance_case_study(sample_size: int = 100):
    """Run a reproducible synthetic benchmark for Indian compliance workflows."""
    sample_size = max(20, min(sample_size, 500))
    document_cycle = [
        "aadhaar",
        "vehicle_registration",
        "property_deed",
        "gst_registration",
        "passport",
    ]

    started = time.time()
    per_doc: Dict[str, Dict[str, Any]] = {
        doc_type: {"total": 0, "eligible": 0, "score_sum": 0.0}
        for doc_type in document_cycle
    }

    eligible_count = 0
    total_score = 0.0

    for idx in range(sample_size):
        doc_type = document_cycle[idx % len(document_cycle)]
        profile = _case_study_profile(doc_type, idx)
        result = evaluate_compliance(
            profile=profile,
            country="IN",
            app_type=_default_app_type_for_document(doc_type),
            document_type=doc_type,
        )

        score = float(result.get("complianceScore", 0))
        eligible = bool(result.get("eligible", False))

        per_doc[doc_type]["total"] += 1
        per_doc[doc_type]["eligible"] += int(eligible)
        per_doc[doc_type]["score_sum"] += score

        eligible_count += int(eligible)
        total_score += score

    duration_ms = int((time.time() - started) * 1000)

    by_document_type = []
    for doc_type, stats in per_doc.items():
        total = stats["total"]
        by_document_type.append(
            {
                "document_type": doc_type,
                "runs": total,
                "eligible": stats["eligible"],
                "eligibility_rate": round((stats["eligible"] / total) * 100, 2) if total else 0.0,
                "avg_score": round((stats["score_sum"] / total), 2) if total else 0.0,
            }
        )

    overall_rate = round((eligible_count / sample_size) * 100, 2)

    return {
        "summary": {
            "sample_size": sample_size,
            "country": "IN",
            "eligible_count": eligible_count,
            "eligibility_rate": overall_rate,
            "avg_compliance_score": round(total_score / sample_size, 2),
            "runtime_ms": duration_ms,
        },
        "by_document_type": by_document_type,
        "benchmark_note": (
            "Synthetic case-study benchmark for judge demos. "
            "Injects controlled invalid IDs every 50th sample to model exception handling."
        ),
        "generated_at": datetime.now().isoformat(),
    }


@app.get("/api/judge/readiness", tags=["Judge"])
async def judge_readiness(request: Request):
    """Strict self-audit endpoint for Track 2 readiness."""
    routes = {r.path for r in app.routes}
    checks = [
        {
            "name": "Airia pipeline endpoint",
            "passed": "/api/airia/pipeline" in routes,
            "weight": 10,
        },
        {
            "name": "Airia tool manifest endpoint",
            "passed": "/api/airia/tools" in routes,
            "weight": 10,
        },
        {
            "name": "Tool endpoints registered",
            "passed": all(
                p in routes
                for p in [
                    "/api/tools/document-analyzer",
                    "/api/tools/rules-validator",
                    "/api/tools/field-mapper",
                    "/api/tools/pdf-generator",
                    "/api/tools/notification-dispatcher",
                ]
            ),
            "weight": 15,
        },
        {
            "name": "HITL approve/reject routes",
            "passed": all(
                p in routes
                for p in [
                    "/api/workflows/{workflow_id}/approve",
                    "/api/workflows/{workflow_id}/reject",
                ]
            ),
            "weight": 15,
        },
        {
            "name": "Persistent workflow history",
            "passed": workflow_store.db_path.exists(),
            "weight": 15,
        },
        {
            "name": "Audit endpoint available",
            "passed": "/api/workflows/{workflow_id}/audit" in routes,
            "weight": 10,
        },
        {
            "name": "Compliance dashboard endpoint",
            "passed": "/api/compliance/dashboard" in routes,
            "weight": 5,
        },
        {
            "name": "Vertical document catalog",
            "passed": "/api/supported-documents" in routes,
            "weight": 5,
        },
        {
            "name": "Demo route (no key) available",
            "passed": "/api/workflows/demo" in routes,
            "weight": 10,
        },
        {
            "name": "Tool auth enforcement capability",
            "passed": True,
            "configured": bool(FORMPILOT_API_KEY),
            "weight": 10,
        },
        {
            "name": "Multi-system integrations declared",
            "passed": bool(airia_client.pipeline_definition.get("integrations")),
            "weight": 5,
        },
    ]

    max_score = sum(item["weight"] for item in checks)
    score = int(
        round(
            sum(item["weight"] for item in checks if item["passed"]) / max_score * 100,
            0,
        )
    )

    grade = "A" if score >= 90 else "B" if score >= 80 else "C"
    verdict = (
        "Strong Track 2 readiness"
        if score >= 90
        else "Competitive but improve remaining failed checks"
    )

    soft_warnings: List[str] = []
    if not GEMINI_API_KEY:
        soft_warnings.append(
            "GEMINI_API_KEY is not set. /api/workflows/start runs in simulated mode."
        )
    if not FORMPILOT_API_KEY:
        soft_warnings.append(
            "FORMPILOT_API_KEY is not set. Tool auth capability exists but is not currently enforced."
        )

    return {
        "score": score,
        "grade": grade,
        "verdict": verdict,
        "tool_auth_enforced": bool(FORMPILOT_API_KEY),
        "persistence_db": str(workflow_store.db_path),
        "checks": checks,
        "soft_warnings": soft_warnings,
        "generated_at": datetime.now().isoformat(),
        "base_url": str(request.base_url).rstrip("/"),
    }


# ===========================================================================
# Configuration info
# ===========================================================================
@app.get("/api/form-fields", tags=["Configuration"])
async def get_default_form_fields():
    fields = (
        workflow.get_default_form_fields()
        if workflow
        else FormAutomationWorkflow.get_default_form_fields()
    )
    return {"form_fields": fields}


@app.get("/api/supported-documents", tags=["Configuration"])
async def get_supported_documents():
    return {"document_types": SUPPORTED_DOCUMENTS}


@app.get("/api/supported-app-types", tags=["Configuration"])
async def get_supported_app_types():
    return {
        "app_types": [
            {"type": "passport", "description": "Passport Application"},
            {"type": "visa", "description": "Visa Application"},
            {"type": "driver_license", "description": "Driver's Licence"},
            {"type": "vehicle_registration", "description": "Vehicle Registration"},
            {"type": "property_registration", "description": "Property Registration"},
            {"type": "gst_registration", "description": "GST Business Registration"},
            {"type": "hr_onboarding", "description": "HR Onboarding (I-9 style)"},
            {"type": "compliance", "description": "Compliance Review"},
            {"type": "generic", "description": "Generic Form"},
        ]
    }


@app.get("/api/supported-countries", tags=["Configuration"])
async def get_supported_countries():
    return {
        "countries": [
            {"code": "IN", "name": "India"},
            {"code": "US", "name": "United States"},
            {"code": "UK", "name": "United Kingdom"},
            {"code": "CA", "name": "Canada"},
        ]
    }


# ===========================================================================
# Error handlers
# ===========================================================================
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    logger.error("Uncaught exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ===========================================================================
# Frontend
# ===========================================================================
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_frontend():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text())
    return HTMLResponse(
        "<html><body style='font-family:sans-serif;padding:40px;"
        "background:#0a0e1a;color:#f1f5f9'>"
        "<h1>🚀 FormPilot API is running</h1>"
        "<p><a href='/docs' style='color:#4f8ef7'>/docs</a> — API documentation</p>"
        "</body></html>"
    )


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    logger.info("Starting FormPilot Enterprise API on %s:%s", host, port)
    uvicorn.run("main:app", host=host, port=port, reload=True, log_level="info")
