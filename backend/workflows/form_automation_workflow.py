"""
FormPilot Workflow Orchestrator
================================
Coordinates the 4-agent pipeline, publishes real-time progress into a shared
state dict (for async polling), handles HITL (human-in-the-loop) approval via
asyncio.Event, and dispatches Slack + SharePoint after PDF generation.

Orchestrator integration: when OrchestratorClient is configured the pipeline is invoked
via the Orchestrator platform; otherwise identical logic runs locally.
"""
import asyncio
import base64
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from agents.agent_1_document_analyzer import DocumentAnalyzerAgent
from agents.agent_2_rules_validator import RulesValidatorAgent
from agents.agent_3_field_mapper import FieldMapperAgent
from agents.agent_4_pdf_generator import PDFGeneratorAgent
from agents.agent_5_browser_submitter import BrowserSubmissionAgent
from agents.base import AgentInput, AgentOutput
from models.schemas import WorkflowOutput

logger = logging.getLogger(__name__)


class FormAutomationWorkflow:
    """
    Orchestrates the 5-step pipeline (4 agents + notification dispatcher):
      1. Document Analyzer  — Gemini Vision OCR
      2. Rules Validator    — government eligibility (+ optional HITL)
      3. Field Mapper       — semantic + fuzzy field matching
      4. PDF Generator      — ReportLab professional PDF
      5. Notifications      — Slack alert + SharePoint upload

    Optionally routes through the external Orchestrator platform when credentials are available.
    """

    def __init__(
        self,
        gemini_api_key: str,
        slack_client=None,
        sharepoint_client=None,
        orchestrator_client=None,
    ) -> None:
        self.gemini_api_key = gemini_api_key
        self.agent_1 = DocumentAnalyzerAgent(gemini_api_key)
        self.agent_2 = RulesValidatorAgent(gemini_api_key)
        self.agent_3 = FieldMapperAgent(gemini_api_key)
        self.agent_4 = PDFGeneratorAgent()
        self.agent_5 = BrowserSubmissionAgent()
        self.slack = slack_client
        self.sharepoint = sharepoint_client
        self.orchestrator = orchestrator_client
        self.workflow_id: Optional[str] = None
        self.start_time: Optional[float] = None
    
    # ------------------------------------------------------------------
    # Helper: update mutable state dict used by the API for polling
    # ------------------------------------------------------------------
    @staticmethod
    def _upd(
        state: Optional[Dict],
        *,
        step: int = None,
        step_name: str = None,
        progress: int = None,
        message: str = None,
        status: str = None,
        **extra,
    ) -> None:
        if state is None:
            return
        if step is not None:
            state["step"] = step
        if step_name is not None:
            state["step_name"] = step_name
        if progress is not None:
            state["progress"] = progress
        if message is not None:
            state["message"] = message
        if status is not None:
            state["status"] = status
        for k, v in extra.items():
            state[k] = v

    @staticmethod
    def _audit_log(state: Optional[Dict], event: str, **details) -> None:
        """Append an audit log entry to the state dict."""
        if state is None:
            return
        if "audit_log" not in state:
            state["audit_log"] = []
        state["audit_log"].append({
            "timestamp": datetime.now().isoformat(),
            "event": event,
            **details,
        })

    # ------------------------------------------------------------------
    # Main execute
    # ------------------------------------------------------------------
    async def execute(
        self,
        workflow_input: Dict[str, Any],
        state: Optional[Dict[str, Any]] = None,
    ) -> WorkflowOutput:
        """
        Execute the complete workflow.

        Args:
            workflow_input: {document_image, document_type, form_fields,
                             country, app_type, form_title,
                             notify_slack, upload_sharepoint, hitl_enabled}
            state: optional mutable dict updated in real-time for polling;
                   must contain 'hitl_event' (asyncio.Event) and
                   'hitl_decision' (None | bool).

        Returns:
            WorkflowOutput with full results.
        """
        
        self.workflow_id = state["workflow_id"] if state else str(uuid.uuid4())
        self.start_time = time.time()

        logger.info("Starting workflow %s", self.workflow_id)
        
        # Initialize audit log
        if state is not None:
            state["audit_log"] = [{
                "timestamp": datetime.now().isoformat(),
                "event": "workflow_start",
                "workflow_id": self.workflow_id,
                "document_type": workflow_input.get("document_type"),
                "country": workflow_input.get("country"),
            }]

        workflow_output = WorkflowOutput(
            workflow_id=self.workflow_id,
            status="in_progress",
        )

        # ------ convenience closure ------
        def upd(**kwargs):
            self._upd(state, **kwargs)

        try:
            # ============================================================
            # Optionally route through Orchestrator Platform (when configured)
            # ============================================================
            if self.orchestrator and self.orchestrator.configured:
                upd(step=0, step_name="Orchestrator Pipeline", progress=5,
                    message="Invoking Orchestrator pipeline…",
                    orchestrator_invoked=True)
                orchestrator_response = await self.orchestrator.invoke_pipeline(workflow_input)
                if orchestrator_response:
                    logger.info("Orchestrator pipeline response received — mapping to WorkflowOutput")
                    # Map Orchestrator response to WorkflowOutput (structure depends on
                    # the Orchestrator pipeline's output schema defined in the YAML)
                    wf_out = orchestrator_response.get("outputs", orchestrator_response)
                    workflow_output.status = "completed"
                    workflow_output.profile = wf_out.get("profile")
                    workflow_output.validation = wf_out.get("validation")
                    workflow_output.mappings = wf_out.get("mappings")
                    workflow_output.pdf_base64 = wf_out.get("pdf_base64")
                    workflow_output.pdf_file_name = wf_out.get("pdf_file_name")
                    workflow_output.message = "Completed via Orchestrator pipeline"
                    workflow_output.completed_at = datetime.now()
                    elapsed_ms = int((time.time() - self.start_time) * 1000)
                    upd(status="completed", progress=100, step=5,
                        step_name="Complete",
                        message=f"Completed via Orchestrator in {elapsed_ms}ms",
                        profile=workflow_output.profile,
                        validation=workflow_output.validation,
                        mappings=workflow_output.mappings,
                        pdf_base64=workflow_output.pdf_base64,
                        pdf_file_name=workflow_output.pdf_file_name,
                        completed_at=datetime.now().isoformat())
                    return workflow_output
                # Orchestrator unavailable — fall through to local execution
                logger.warning("Orchestrator pipeline returned nothing; falling back to local execution.")
                upd(orchestrator_invoked=False)

            # ============================================================
            # Agent 1: Document Analysis
            # ============================================================
            upd(step=1, step_name="Document Analyzer", progress=10,
                message="🔍 Analyzing document with Gemini 2.0 Flash Vision…")

            a1_result = await self.agent_1.run(AgentInput(
                workflow_id=self.workflow_id,
                metadata={
                    "document_image": workflow_input.get("document_image"),
                    "document_type": workflow_input.get("document_type", "generic"),
                },
            ))

            if a1_result.status == "error":
                upd(status="failed", message="Document analysis failed",
                    errors=a1_result.errors)
                workflow_output.status = "failed"
                workflow_output.errors = a1_result.errors
                workflow_output.message = "Document analysis failed"
                return workflow_output

            profile = a1_result.data.get("profile", a1_result.data)
            upd(step=1, progress=30,
                message=f"✅ Document analyzed — confidence {a1_result.confidence:.0%}",
                profile=profile)
            logger.info("[%s] Agent 1 done — confidence %.2f",
                        self.workflow_id, a1_result.confidence)

            # ============================================================
            # Agent 2: Rules Validation
            # ============================================================
            upd(step=2, step_name="Rules Validator", progress=35,
                message="✅ Validating government eligibility rules…")

            a2_result = await self.agent_2.run(AgentInput(
                workflow_id=self.workflow_id,
                metadata={
                    "profile": profile,
                    "country": workflow_input.get("country", "IN"),
                    "app_type": workflow_input.get("app_type", "passport"),
                    "document_type": workflow_input.get("document_type", profile.get("documentType", "generic")),
                },
            ))

            validation = a2_result.data
            upd(validation=validation)

            # ---- HITL (Human-In-The-Loop) ----
            eligible = validation.get("eligible", True)
            hitl_enabled = workflow_input.get("hitl_enabled", True)

            if not eligible and hitl_enabled and state is not None:
                logger.info("[%s] Eligibility failed — triggering HITL", self.workflow_id)
                self._audit_log(state, "hitl_triggered",
                               workflow_id=self.workflow_id,
                               reason=validation.get("notes"),
                               failed_checks=validation.get("validationResults", []))
                upd(status="awaiting_approval", step=2,
                    progress=40,
                    message="⚠️ Eligibility check failed — awaiting human review…")

                # Send Slack HITL request
                if self.slack:
                    app_base = workflow_input.get("app_base_url", "")
                    await self.slack.send_hitl_request(
                        self.workflow_id, profile, validation, app_base
                    )

                # Wait for HITL decision (with 5-minute timeout)
                hitl_event: asyncio.Event = state.get("hitl_event")
                if hitl_event:
                    try:
                        await asyncio.wait_for(hitl_event.wait(), timeout=300)
                    except asyncio.TimeoutError:
                        logger.warning("[%s] HITL timeout — auto-rejecting", self.workflow_id)
                        state["hitl_decision"] = False
                        self._audit_log(state, "hitl_timeout",
                                       workflow_id=self.workflow_id,
                                       decision="rejected")

                    approved = state.get("hitl_decision", False)
                    if not approved:
                        self._audit_log(state, "hitl_decision",
                                       workflow_id=self.workflow_id,
                                       decision="rejected")
                        upd(status="rejected", progress=0,
                            message="❌ Workflow rejected by reviewer (eligibility failed)")
                        workflow_output.status = "rejected"
                        workflow_output.message = "Rejected by human reviewer"
                        return workflow_output

                    self._audit_log(state, "hitl_decision",
                                   workflow_id=self.workflow_id,
                                   decision="approved")
                    upd(status="running", progress=40,
                        message="✅ Human reviewer approved — continuing pipeline…")

            upd(step=2, progress=45,
                message=f"✅ Validation complete — {'eligible' if eligible else 'approved by reviewer'}")

            # ============================================================
            # Agent 3: Field Mapping
            # ============================================================
            browser_config = workflow_input.get("browser_automation") or {}
            if browser_config.get("target_url") and not workflow_input.get("form_fields"):
                upd(step=3, step_name="Field Mapper", progress=48,
                    message="🌐 Discovering live form fields with Playwright…")
                discovery = await self.agent_5.discover_form_fields(
                    browser_config["target_url"],
                    headless=bool(browser_config.get("headless", True)),
                    timeout_ms=int(browser_config.get("timeout_ms", 30000)),
                )
                workflow_input["form_fields"] = discovery.get("fields", [])
                upd(portal_fields=workflow_input["form_fields"])
                self._audit_log(
                    state,
                    "portal_fields_discovered",
                    workflow_id=self.workflow_id,
                    target_url=browser_config["target_url"],
                    field_count=len(workflow_input["form_fields"]),
                )

            upd(step=3, step_name="Field Mapper", progress=50,
                message="🗺️ Semantically mapping fields with Gemini…")

            a3_result = await self.agent_3.run(AgentInput(
                workflow_id=self.workflow_id,
                metadata={
                    "profile": profile,
                    "form_fields": workflow_input.get("form_fields", []),
                    "country": workflow_input.get("country", "IN"),
                    "app_type": workflow_input.get("app_type", "passport"),
                },
            ))

            if a3_result.status == "error":
                upd(status="failed", message="Field mapping failed", errors=a3_result.errors)
                workflow_output.status = "failed"
                workflow_output.errors = a3_result.errors
                workflow_output.message = "Field mapping failed"
                return workflow_output

            mappings = a3_result.data.get("mappings", [])
            upd(step=3, progress=65,
                message=f"✅ Field mapper complete — {len(mappings)} fields mapped",
                mappings=mappings)

            # ============================================================
            # Agent 4: PDF Generation
            # ============================================================
            upd(step=4, step_name="PDF Generator", progress=70,
                message="📄 Generating professional PDF with ReportLab…")

            a4_result = await self.agent_4.run(AgentInput(
                workflow_id=self.workflow_id,
                metadata={
                    "mappings": mappings,
                    "profile": profile,
                    "form_title": workflow_input.get("form_title", "Filled Form"),
                },
            ))

            if a4_result.status == "error":
                upd(status="failed", message="PDF generation failed", errors=a4_result.errors)
                workflow_output.status = "failed"
                workflow_output.errors = a4_result.errors
                workflow_output.message = "PDF generation failed"
                return workflow_output

            pdf_base64 = a4_result.data.get("pdf_base64")
            pdf_bytes_data = a4_result.data.get("pdf_bytes")
            file_name = a4_result.data.get("file_name")
            upd(step=4, progress=82,
                message="✅ PDF generated successfully",
                pdf_base64=pdf_base64,
                pdf_file_name=file_name)
            logger.info("[%s] Agent 4 done — PDF generated", self.workflow_id)

            browser_submission = None
            if browser_config.get("target_url"):
                upd(step=5, step_name="Browser Submitter", progress=88,
                    message="🌐 Launching headless Chromium for live form submission…")
                a5_result = await self.agent_5.run(AgentInput(
                    workflow_id=self.workflow_id,
                    metadata={
                        "profile": profile,
                        "mappings": mappings,
                        "browser_automation": browser_config,
                    },
                ))

                # =============== NEW: Browser HITL Handling ===============
                if a5_result.status == "awaiting_user_interaction":
                    # User must solve CAPTCHA/OTP/password gate before we proceed
                    browser_submission = a5_result.data
                    interaction_type = browser_submission.get("interaction_type", "solve_security_challenge")
                    interaction_prompt = browser_submission.get("interaction_prompt", "")
                    session_id = browser_submission.get("interaction_session_id")
                    
                    logger.info("[%s] Browser HITL triggered — interaction type: %s", 
                               self.workflow_id, interaction_type)
                    
                    self._audit_log(
                        state,
                        "browser_interaction_required",
                        workflow_id=self.workflow_id,
                        interaction_type=interaction_type,
                        session_id=session_id,
                        prompt=interaction_prompt,
                    )
                    
                    upd(
                        status="awaiting_user_interaction",
                        step=5,
                        progress=90,
                        message=f"🔒 Awaiting user to complete: {interaction_type}",
                        current_interaction_type=interaction_type,
                        browser_submission=browser_submission,
                    )
                    
                    # Send notification with instructions
                    if self.slack:
                        app_base = workflow_input.get("app_base_url", "")
                        await self.slack.send_browser_interaction_request(
                            self.workflow_id,
                            interaction_type,
                            interaction_prompt,
                            app_base,
                        )
                    
                    # Return immediately — wait for user to call resume endpoint
                    workflow_output.status = "awaiting_user_interaction"
                    workflow_output.browser_submission = browser_submission
                    workflow_output.message = interaction_prompt
                    return workflow_output
                # =============== END Browser HITL Handling ===============

                elif a5_result.status == "error":
                    upd(status="failed", message="Browser submission failed", errors=a5_result.errors)
                    workflow_output.status = "failed"
                    workflow_output.errors = a5_result.errors
                    workflow_output.message = "Browser submission failed"
                    return workflow_output

                else:  # a5_result.status == "success"
                    browser_submission = a5_result.data
                    upd(step=5, progress=92,
                        message="✅ Browser automation completed",
                        browser_submission=browser_submission)
                
                self._audit_log(
                    state,
                    "browser_submission_completed",
                    workflow_id=self.workflow_id,
                    target_url=browser_config["target_url"],
                    submitted=browser_submission.get("submitted", False),
                    resolved_url=browser_submission.get("resolved_url"),
                )

            # ============================================================
            # Step 5: Notifications (Slack + SharePoint)
            # ============================================================
            upd(step=5, step_name="Notification Dispatcher", progress=94,
                message="📢 Dispatching Slack notification & SharePoint upload…")

            slack_sent = False
            sharepoint_url = None

            notify_slack = workflow_input.get("notify_slack", True)
            upload_sharepoint = workflow_input.get("upload_sharepoint", True)
            app_base = workflow_input.get("app_base_url", "")

            if self.slack and notify_slack:
                slack_sent = await self.slack.send_completion_notification(
                    self.workflow_id, profile, file_name or "", validation, app_base
                )
                upd(slack_sent=slack_sent)

            if self.sharepoint and upload_sharepoint and pdf_bytes_data:
                pdf_bytes: bytes = (
                    pdf_bytes_data
                    if isinstance(pdf_bytes_data, bytes)
                    else base64.b64decode(pdf_bytes_data)
                )
                sharepoint_url = await self.sharepoint.upload_pdf(
                    pdf_bytes,
                    file_name or "formpilot_output.pdf",
                    {
                        "applicant": (profile.get("fullName") or {}).get("value", "Unknown"),
                        "document_type": workflow_input.get("document_type", ""),
                        "workflow_id": self.workflow_id,
                    },
                )
                upd(sharepoint_url=sharepoint_url)

            # ============================================================
            # Complete
            # ============================================================
            elapsed_ms = int((time.time() - self.start_time) * 1000)

            workflow_output.status = "completed"
            workflow_output.profile = profile
            workflow_output.validation = validation
            workflow_output.mappings = mappings
            workflow_output.portal_fields = workflow_input.get("form_fields")
            workflow_output.browser_submission = browser_submission
            workflow_output.pdf_base64 = pdf_base64
            workflow_output.pdf_file_name = file_name
            workflow_output.completed_at = datetime.now()
            workflow_output.message = f"Pipeline completed in {elapsed_ms}ms"

            upd(status="completed", progress=100, step=5,
                step_name="Complete",
                message=f"🎉 Pipeline complete in {elapsed_ms}ms",
                completed_at=datetime.now().isoformat(),
                slack_sent=slack_sent,
                sharepoint_url=sharepoint_url)

            logger.info(
                "[%s] Workflow complete in %dms | doc=%.2f mapping=%.2f | "
                "slack=%s sharepoint=%s",
                self.workflow_id, elapsed_ms,
                a1_result.confidence, a3_result.confidence,
                slack_sent, bool(sharepoint_url),
            )
            
            # Log workflow completion
            self._audit_log(state, "workflow_completed",
                           workflow_id=self.workflow_id,
                           elapsed_ms=elapsed_ms,
                           slack_sent=slack_sent,
                           sharepoint_uploaded=bool(sharepoint_url))
            
            return workflow_output

        except Exception as exc:
            logger.error("[%s] Workflow error: %s", self.workflow_id, exc, exc_info=True)
            workflow_output.status = "failed"
            workflow_output.errors = [str(exc)]
            workflow_output.message = f"Unexpected error: {exc}"
            upd(status="failed", message=f"❌ {exc}", errors=[str(exc)])
            
            # Log workflow failure
            self._audit_log(state, "workflow_failed",
                           workflow_id=self.workflow_id,
                           error=str(exc))

            if self.slack:
                try:
                    await self.slack.send_error_notification(self.workflow_id, str(exc))
                except Exception:
                    pass

            return workflow_output

    # ------------------------------------------------------------------
    # Default form fields
    # ------------------------------------------------------------------
    @staticmethod
    def get_default_form_fields() -> list:
        """Return default enterprise form field definitions."""
        return [
            {"name": "fullName",     "label": "Full Name",         "required": True},
            {"name": "firstName",    "label": "First Name",         "required": True},
            {"name": "lastName",     "label": "Last Name",          "required": True},
            {"name": "dateOfBirth",  "label": "Date of Birth",      "required": True},
            {"name": "gender",       "label": "Gender",             "required": True},
            {"name": "address",      "label": "Street Address",     "required": True},
            {"name": "city",         "label": "City",               "required": True},
            {"name": "state",        "label": "State / Province",   "required": True},
            {"name": "pincode",      "label": "Postal Code",        "required": True},
            {"name": "country",      "label": "Country",            "required": False},
            {"name": "documentId",   "label": "Document ID",        "required": True},
            {"name": "documentType", "label": "Document Type",      "required": True},
            {"name": "vehicleNumber", "label": "Vehicle Registration Number", "required": False},
            {"name": "propertyDeedId", "label": "Property Deed Reference", "required": False},
            {"name": "gstin", "label": "GSTIN", "required": False},
            {"name": "nationality",  "label": "Nationality",        "required": False},
            {"name": "phone",        "label": "Phone Number",       "required": False},
            {"name": "email",        "label": "Email Address",      "required": False},
        ]
