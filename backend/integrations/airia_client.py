"""
Airia AI Platform Orchestration Client
=======================================
Wraps FormPilot agents as Airia-callable HTTP tool endpoints and enables
pipeline orchestration through the Airia platform.

When AIRIA_API_KEY + AIRIA_PIPELINE_ID are configured, the workflow is
routed through the Airia pipeline engine.  Without credentials the system
falls back to identical local orchestration — same agents, same logic.

Airia Community pipeline: https://community.airia.io/FormPilot
Track: Track 2 — Active Agents
"""

import os
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pipeline definition (mirrors what is published to Airia Community)
# ---------------------------------------------------------------------------
AIRIA_PIPELINE_DEFINITION: Dict[str, Any] = {
    "name": "FormPilot — Document-to-Form Pipeline",
    "version": "2.0.0",
    "description": (
        "Enterprise multi-agent pipeline: extract identity from ID documents, "
        "validate government eligibility (with HITL), map form fields, "
        "generate PDF, dispatch Slack alert & upload to SharePoint."
    ),
    "track": "Track 2 — Active Agents",
    "steps": [
        {
            "id": "analyze_document",
            "name": "Document Analyzer",
            "icon": "🔍",
            "agent": "FormPilot/DocumentAnalyzer",
            "tool_endpoint": "/api/tools/document-analyzer",
            "description": "Extract structured identity using Gemini Pro Vision",
            "hitl": False,
        },
        {
            "id": "validate_rules",
            "name": "Rules Validator",
            "icon": "✅",
            "agent": "FormPilot/RulesValidator",
            "tool_endpoint": "/api/tools/rules-validator",
            "description": "Validate eligibility against government rules (4 countries)",
            "hitl": {
                "enabled": True,
                "trigger": "validation.eligible == false",
                "message": "Eligibility check failed — human review required",
                "timeout_seconds": 300,
                "on_timeout": "reject",
            },
        },
        {
            "id": "map_fields",
            "name": "Field Mapper",
            "icon": "🗺️",
            "agent": "FormPilot/FieldMapper",
            "tool_endpoint": "/api/tools/field-mapper",
            "description": "Semantically map extracted identity data to form fields",
            "hitl": False,
        },
        {
            "id": "generate_pdf",
            "name": "PDF Generator",
            "icon": "📄",
            "agent": "FormPilot/PDFGenerator",
            "tool_endpoint": "/api/tools/pdf-generator",
            "description": "Generate professional government-ready PDF",
            "hitl": False,
        },
        {
            "id": "dispatch_notifications",
            "name": "Notification Dispatcher",
            "icon": "📢",
            "agent": "FormPilot/NotificationDispatcher",
            "tool_endpoint": "/api/tools/notification-dispatcher",
            "description": "Send Slack notification and upload PDF to SharePoint",
            "hitl": False,
        },
    ],
    "integrations": {
        "slack": {
            "type": "slack_incoming_webhook",
            "env": "SLACK_WEBHOOK_URL",
            "description": "Rich Block Kit completion & HITL notifications",
        },
        "sharepoint": {
            "type": "microsoft_sharepoint",
            "env": ["SHAREPOINT_TENANT_ID", "SHAREPOINT_CLIENT_ID", "SHAREPOINT_SITE_URL"],
            "description": "PDF storage via Microsoft Graph API",
        },
    },
}


class AiriaClient:
    """
    Client for the Airia AI Platform.

    Exposes FormPilot agents as Airia-callable HTTP tools and supports
    Airia-orchestrated pipeline execution when credentials are available.
    """

    AIRIA_BASE_URL = "https://api.airia.io"

    def __init__(
        self,
        api_key: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("AIRIA_API_KEY")
        self.pipeline_id = pipeline_id or os.getenv("AIRIA_PIPELINE_ID")
        self.base_url = base_url or os.getenv("AIRIA_BASE_URL", self.AIRIA_BASE_URL)
        self.configured = bool(self.api_key and self.pipeline_id)

        if self.configured:
            logger.info("Airia client ready — pipeline: %s", self.pipeline_id)
        else:
            logger.info(
                "Airia credentials absent — running local orchestration mode. "
                "Set AIRIA_API_KEY + AIRIA_PIPELINE_ID to route through Airia."
            )

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def invoke_pipeline(
        self, inputs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Invoke the remote Airia pipeline.

        Returns the Airia response dict on success, None when not configured
        or when the call fails (caller falls back to local orchestration).
        """
        if not self.configured:
            return None

        url = f"{self.base_url}/v1/pipelines/{self.pipeline_id}/execute"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    url,
                    headers={
                        "X-Airia-Api-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={"inputs": inputs},
                )
                resp.raise_for_status()
                logger.info("Airia pipeline invocation succeeded.")
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Airia pipeline HTTP error %s: %s",
                exc.response.status_code,
                exc.response.text[:300],
            )
        except Exception as exc:
            logger.error("Airia pipeline error: %s", exc)
        return None

    # ------------------------------------------------------------------
    # Tool manifest (for Airia tool registry)
    # ------------------------------------------------------------------

    def get_tool_manifest(self, base_url: str) -> Dict[str, Any]:
        """
        Return the OpenAPI-compatible tool manifest Airia uses to discover
        and call our agent tool endpoints.
        """
        return {
            "name": "FormPilot",
            "version": "2.0.0",
            "description": "AI-powered document-to-form pipeline tools",
            "base_url": base_url,
            "auth": {"type": "bearer", "env": "FORMPILOT_API_KEY"},
            "tools": [
                {
                    "name": "document_analyzer",
                    "endpoint": "/api/tools/document-analyzer",
                    "method": "POST",
                    "description": "Extract structured identity from a document image",
                    "parameters": {
                        "document_image": {
                            "type": "string",
                            "description": "Base64-encoded identity document image",
                        },
                        "document_type": {
                            "type": "string",
                            "enum": ["aadhaar", "passport", "pan", "driving_license", "generic"],
                        },
                        "workflow_id": {"type": "string"},
                    },
                    "required": ["document_image"],
                },
                {
                    "name": "rules_validator",
                    "endpoint": "/api/tools/rules-validator",
                    "method": "POST",
                    "description": "Validate identity against government eligibility rules",
                    "parameters": {
                        "profile": {"type": "object"},
                        "country": {"type": "string", "enum": ["IN", "US", "UK", "CA"]},
                        "app_type": {"type": "string"},
                        "workflow_id": {"type": "string"},
                    },
                    "required": ["profile", "country"],
                },
                {
                    "name": "field_mapper",
                    "endpoint": "/api/tools/field-mapper",
                    "method": "POST",
                    "description": "Semantically map identity data to form fields",
                    "parameters": {
                        "profile": {"type": "object"},
                        "form_fields": {"type": "array"},
                        "workflow_id": {"type": "string"},
                    },
                    "required": ["profile"],
                },
                {
                    "name": "pdf_generator",
                    "endpoint": "/api/tools/pdf-generator",
                    "method": "POST",
                    "description": "Generate a professional PDF from mapped fields",
                    "parameters": {
                        "mappings": {"type": "array"},
                        "profile": {"type": "object"},
                        "form_title": {"type": "string"},
                        "workflow_id": {"type": "string"},
                    },
                    "required": ["mappings", "profile"],
                },
                {
                    "name": "notification_dispatcher",
                    "endpoint": "/api/tools/notification-dispatcher",
                    "method": "POST",
                    "description": "Send Slack notification and upload to SharePoint",
                    "parameters": {
                        "workflow_id": {"type": "string"},
                        "profile": {"type": "object"},
                        "validation": {"type": "object"},
                        "pdf_file_name": {"type": "string"},
                        "pdf_base64": {"type": "string"},
                        "notify_slack": {"type": "boolean", "default": True},
                        "upload_sharepoint": {"type": "boolean", "default": True},
                    },
                    "required": ["workflow_id"],
                },
            ],
        }

    # ------------------------------------------------------------------
    # Pipeline definition accessor
    # ------------------------------------------------------------------

    @property
    def pipeline_definition(self) -> Dict[str, Any]:
        return AIRIA_PIPELINE_DEFINITION

    def get_pipeline_steps(self) -> List[Dict[str, Any]]:
        return AIRIA_PIPELINE_DEFINITION["steps"]
