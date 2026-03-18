"""
Slack Integration Client
========================
Sends FormPilot workflow notifications to Slack via Incoming Webhooks.

Supports:
  • Rich Block Kit completion notifications
  • HITL approval request messages with action buttons
  • Error alert messages

Set SLACK_WEBHOOK_URL in .env to enable.  All methods return False (no-op)
when the webhook is not configured — the workflow still completes normally.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class SlackClient:
    """Slack Incoming Webhook client for FormPilot notifications."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> None:
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.channel = channel or os.getenv("SLACK_CHANNEL", "#formpilot-notifications")
        self.configured = bool(self.webhook_url)

        if not self.configured:
            logger.info(
                "Slack not configured — set SLACK_WEBHOOK_URL to enable notifications."
            )

    # ------------------------------------------------------------------
    # Public notification methods
    # ------------------------------------------------------------------

    async def send_completion_notification(
        self,
        workflow_id: str,
        profile: Dict[str, Any],
        pdf_file_name: str,
        validation: Dict[str, Any],
        app_base_url: str = "",
    ) -> bool:
        """Send a rich completion notification when a workflow finishes."""
        if not self.configured:
            return False

        name = self._field_value(profile, "fullName")
        doc_type = profile.get("documentType", "Document")
        eligible = validation.get("eligible", True)
        confidence = profile.get("overallConfidence", 0)
        timestamp = datetime.now(timezone.utc).strftime("%d %b %Y  %H:%M UTC")
        conf_pct = f"{confidence * 100:.0f}%" if isinstance(confidence, float) else "—"

        blocks: List[Dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✅  FormPilot — Form Ready for Download",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Applicant*\n{name}"},
                    {"type": "mrkdwn", "text": f"*Document*\n{doc_type}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Eligibility*\n{'✅  Eligible' if eligible else '⚠️  Review needed'}",
                    },
                    {"type": "mrkdwn", "text": f"*OCR Confidence*\n{conf_pct}"},
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"📄  *File:* `{pdf_file_name}`\n"
                        f"🤖  *Pipeline:* Airia  ·  4-Agent Workflow  ·  Gemini 2.0 Flash\n"
                        f"🕐  *Completed:* {timestamp}"
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Workflow `{workflow_id[:12]}…`  ·  FormPilot Enterprise v2.0",
                    }
                ],
            },
        ]

        return await self._post_blocks(blocks)

    async def send_hitl_request(
        self,
        workflow_id: str,
        profile: Dict[str, Any],
        validation: Dict[str, Any],
        app_base_url: str = "",
    ) -> bool:
        """
        Send a HITL (human-in-the-loop) approval request.

        Includes deep-link buttons that call the approve / reject endpoints.
        When the reviewer clicks a button, the workflow resumes or rejects.
        """
        if not self.configured:
            return False

        name = self._field_value(profile, "fullName")
        notes = validation.get("notes", "Eligibility check raised issues.")

        failed: List[str] = [
            f"• *{r.get('check', '?')}*: {r.get('explanation', '')}"
            for r in validation.get("validationResults", [])
            if not r.get("passed", True)
        ]
        failed_text = "\n".join(failed) if failed else "See validation details above."

        approve_url = f"{app_base_url}/api/workflows/{workflow_id}/approve"
        reject_url = f"{app_base_url}/api/workflows/{workflow_id}/reject"

        blocks: List[Dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️  Human Review Required — FormPilot",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Applicant:* {name}\n"
                        f"*Issue:* {notes}\n\n"
                        f"*Failed checks:*\n{failed_text}"
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Does this application pass your review? Click to continue or stop processing.",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅  Approve & Continue", "emoji": True},
                        "style": "primary",
                        "url": approve_url,
                        "action_id": "formpilot_approve",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌  Reject", "emoji": True},
                        "style": "danger",
                        "url": reject_url,
                        "action_id": "formpilot_reject",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"Workflow `{workflow_id[:12]}…`  ·  "
                            f"Auto-rejects in 5 min if no action is taken."
                        ),
                    }
                ],
            },
        ]

        return await self._post_blocks(blocks)

    async def send_browser_interaction_request(
        self,
        workflow_id: str,
        interaction_type: str,
        interaction_prompt: str,
        app_base_url: str = "",
    ) -> bool:
        """
        Send a browser interaction request (CAPTCHA, OTP, password gate, etc.).
        
        User must complete the challenge in the browser, then click "Completed"
        button to resume form submission.
        """
        if not self.configured:
            return False

        # Format interaction type for display
        type_labels = {
            "solve_captcha": "🔐 CAPTCHA Challenge",
            "enter_otp": "📱 OTP Verification",
            "solve_password_gate": "🔑 Password Authentication",
            "solve_security_challenge": "🛡️ Security Challenge",
        }
        type_label = type_labels.get(interaction_type, "Security Challenge")

        resume_url = f"{app_base_url}/api/workflows/{workflow_id}/browser-interaction/resume"

        blocks: List[Dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{type_label} — FormPilot Form Submission",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Action Required:*\n"
                        f"{interaction_prompt}\n\n"
                        f"Once you've completed the security challenge, click the button below "
                        f"to resume form submission."
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Challenge Completed — Resume Submit",
                            "emoji": True,
                        },
                        "style": "primary",
                        "url": resume_url,
                        "action_id": "formpilot_browser_resume",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"Workflow `{workflow_id[:12]}…`  ·  "
                            f"Session will timeout in 5 minutes of inactivity."
                        ),
                    }
                ],
            },
        ]

        return await self._post_blocks(blocks)

    async def send_error_notification(self, workflow_id: str, error: str) -> bool:
        """Send an error alert."""
        if not self.configured:
            return False

        blocks: List[Dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "❌  FormPilot — Workflow Failed",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Workflow ID:* `{workflow_id}`\n*Error:* {error}",
                },
            },
        ]

        return await self._post_blocks(blocks)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _post_blocks(self, blocks: List[Dict]) -> bool:
        payload: Dict[str, Any] = {"blocks": blocks}
        if self.channel:
            payload["channel"] = self.channel

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    logger.info("Slack notification sent ✓")
                    return True
                logger.warning("Slack responded %s: %s", resp.status_code, resp.text[:200])
                return False
        except Exception as exc:
            logger.error("Slack notification failed: %s", exc)
            return False

    @staticmethod
    def _field_value(profile: Dict[str, Any], field: str) -> str:
        val = profile.get(field, {})
        if isinstance(val, dict):
            return val.get("value", "Unknown")
        return str(val) if val else "Unknown"
