#!/usr/bin/env python3
"""Run an end-to-end smoke test for the FormPilot Chrome extension."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
EXTENSION_DIR = ROOT / "extension" / "formpilot-autofill"
SANDBOX_URL = "http://127.0.0.1:8010/static/extension_sandbox.html"
API_BASE = "http://127.0.0.1:8010"


def wait_for_server(url: str, timeout_s: float = 25.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            res = requests.get(url, timeout=2)
            if res.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.4)
    raise RuntimeError(f"Server did not become ready: {url}")


def write_sample_image(path: Path) -> None:
    png_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Yha0X4AAAAASUVORK5CYII="
    )
    path.write_bytes(base64.b64decode(png_base64))


def run_test() -> Dict[str, str]:
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8010"],
        cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        wait_for_server(f"{API_BASE}/health")

        with tempfile.TemporaryDirectory(prefix="formpilot-ext-userdata-") as user_data_dir, tempfile.TemporaryDirectory(
            prefix="formpilot-ext-assets-"
        ) as assets_dir:
            sample_path = Path(assets_dir) / "sample_identity.png"
            write_sample_image(sample_path)

            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    ignore_default_args=["--disable-extensions"],
                    args=[
                        f"--disable-extensions-except={EXTENSION_DIR}",
                        f"--load-extension={EXTENSION_DIR}",
                    ],
                )

                try:
                    service_worker = (
                        context.service_workers[0]
                        if context.service_workers
                        else context.wait_for_event("serviceworker", timeout=30000)
                    )
                    extension_id = service_worker.url.split("/")[2]

                    page = context.new_page()
                    page.goto(SANDBOX_URL, wait_until="domcontentloaded")
                    page.wait_for_selector("#fullName", timeout=15000)

                    popup = context.new_page()
                    popup.goto(f"chrome-extension://{extension_id}/popup.html")

                    tab_id = popup.evaluate(
                        """
                        () => new Promise((resolve) => {
                          chrome.tabs.query({ url: 'http://127.0.0.1:8010/static/extension_sandbox.html*' }, (tabs) => {
                            resolve(tabs && tabs[0] ? tabs[0].id : null);
                          });
                        })
                        """
                    )

                    if tab_id is None:
                        raise RuntimeError("Could not find sandbox tab from extension context.")

                    popup.goto(f"chrome-extension://{extension_id}/popup.html?tabId={tab_id}")
                    popup.fill("#apiBase", API_BASE)
                    popup.select_option("#documentType", "passport")
                    popup.select_option("#country", "IN")
                    popup.select_option("#appType", "passport")
                    popup.set_input_files("#identityFile", str(sample_path))
                    popup.click("#runBtn")

                    popup.wait_for_function(
                        """
                        () => {
                          const text = document.querySelector('#status')?.textContent || '';
                          return text.startsWith('Done. Filled');
                        }
                        """,
                        timeout=120000,
                    )

                    values = page.evaluate(
                        """
                        () => ({
                          fullName: document.querySelector('#fullName')?.value || '',
                          dob: document.querySelector('#dateOfBirth')?.value || '',
                          gender: document.querySelector('#gender')?.value || '',
                          city: document.querySelector('#city')?.value || '',
                          pincode: document.querySelector('#pincode')?.value || '',
                          documentId: document.querySelector('#documentId')?.value || ''
                        })
                        """
                    )

                    if not values["fullName"] or not values["documentId"]:
                        raise RuntimeError(f"Autofill failed, received values: {values}")

                    return {
                        "fullName": values["fullName"],
                        "documentId": values["documentId"],
                        "city": values["city"],
                        "pincode": values["pincode"],
                    }
                finally:
                    context.close()
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(f"Playwright timeout: {exc}") from exc
    finally:
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            backend_proc.kill()


def main() -> int:
    if not EXTENSION_DIR.exists():
        print(f"Extension directory missing: {EXTENSION_DIR}", file=sys.stderr)
        return 1

    try:
        result = run_test()
    except Exception as exc:
        print(f"Extension smoke test failed: {exc}", file=sys.stderr)
        return 1

    print("Extension smoke test passed.")
    print(f"Filled fullName={result['fullName']}")
    print(f"Filled documentId={result['documentId']}")
    print(f"Filled city={result['city']}")
    print(f"Filled pincode={result['pincode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
