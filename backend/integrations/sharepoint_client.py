"""
Microsoft SharePoint Integration Client
========================================
Uploads FormPilot-generated PDFs to a SharePoint document library using
the Microsoft Graph API with OAuth 2.0 client-credentials flow (app-only
auth, no user interaction required — ideal for automated pipelines).

Required environment variables:
    SHAREPOINT_TENANT_ID      — Azure AD / Entra ID tenant ID
    SHAREPOINT_CLIENT_ID      — App registration client ID
    SHAREPOINT_CLIENT_SECRET  — App registration client secret
    SHAREPOINT_SITE_URL       — e.g. https://contoso.sharepoint.com/sites/formpilot
    SHAREPOINT_LIBRARY        — Document library name (default: FormPilot Documents)

All public methods return None / False when credentials are missing —
the workflow completes normally without SharePoint upload.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class SharePointClient:
    """Uploads PDFs to SharePoint via Microsoft Graph API."""

    def __init__(self) -> None:
        self.tenant_id = os.getenv("SHAREPOINT_TENANT_ID")
        self.client_id = os.getenv("SHAREPOINT_CLIENT_ID")
        self.client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
        self.site_url = os.getenv("SHAREPOINT_SITE_URL", "").rstrip("/")
        self.library = os.getenv("SHAREPOINT_LIBRARY", "FormPilot Documents")

        self.configured = bool(
            self.tenant_id
            and self.client_id
            and self.client_secret
            and self.site_url
        )

        if not self.configured:
            logger.info(
                "SharePoint not configured — set SHAREPOINT_TENANT_ID, "
                "SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET, SHAREPOINT_SITE_URL."
            )

    # ------------------------------------------------------------------
    # Public upload method
    # ------------------------------------------------------------------

    async def upload_pdf(
        self,
        pdf_bytes: bytes,
        file_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Upload a PDF to the configured SharePoint library.

        Files are placed under <library>/<YYYY-MM-DD>/<file_name>.
        Returns the SharePoint webUrl of the uploaded file, or None on failure.
        """
        if not self.configured:
            logger.info("SharePoint not configured — skipping upload.")
            return None

        token = await self._get_token()
        if not token:
            return None

        site_id = await self._get_site_id(token)
        if not site_id:
            return None

        date_folder = datetime.now().strftime("%Y-%m-%d")
        folder_path = f"{self.library}/{date_folder}"
        upload_url = (
            f"{GRAPH_BASE}/sites/{site_id}"
            f"/drive/root:/{folder_path}/{file_name}:/content"
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.put(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/pdf",
                    },
                    content=pdf_bytes,
                )
                resp.raise_for_status()
                web_url: str = resp.json().get("webUrl", "")
                logger.info("SharePoint upload OK: %s", web_url)
                return web_url
        except httpx.HTTPStatusError as exc:
            logger.error(
                "SharePoint upload HTTP %s: %s",
                exc.response.status_code,
                exc.response.text[:300],
            )
        except Exception as exc:
            logger.error("SharePoint upload error: %s", exc)
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_token(self) -> Optional[str]:
        """Obtain an access token via client-credentials grant."""
        token_url = (
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "scope": "https://graph.microsoft.com/.default",
                    },
                )
                resp.raise_for_status()
                return resp.json().get("access_token")
        except Exception as exc:
            logger.error("SharePoint token error: %s", exc)
            return None

    async def _get_site_id(self, token: str) -> Optional[str]:
        """Resolve the site URL to a Graph site ID."""
        try:
            parsed = urlparse(self.site_url)
            hostname = parsed.hostname
            site_path = parsed.path.rstrip("/")
            url = f"{GRAPH_BASE}/sites/{hostname}:{site_path}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    url, headers={"Authorization": f"Bearer {token}"}
                )
                resp.raise_for_status()
                return resp.json().get("id")
        except Exception as exc:
            logger.error("SharePoint site lookup error: %s", exc)
            return None
