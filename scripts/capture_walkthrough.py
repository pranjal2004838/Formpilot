from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "assets" / "screenshots"
TEST_DATA_DIR = ROOT / "assets" / "test-data"


def save(page, name: str, full_page: bool = False) -> None:
    target = SCREENSHOT_DIR / name
    page.screenshot(path=str(target), full_page=full_page)
    print(f"saved: {target.relative_to(ROOT)}")


def run() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    document_file = TEST_DATA_DIR / "synthetic_aadhaar.png"
    if not document_file.exists():
        raise FileNotFoundError(f"Missing test document: {document_file}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1720, "height": 980})

        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_timeout(1000)

        # 1) Landing page
        save(page, "01_home_hero.png")

        # 2) Demo section before upload
        page.evaluate(
            "document.getElementById('demo').scrollIntoView({behavior:'instant', block:'start'})"
        )
        page.wait_for_timeout(900)
        save(page, "02_demo_section.png")

        # 3) Upload synthetic identity doc
        page.set_input_files("#fileInput", str(document_file))
        page.wait_for_selector("#uploadPreview.show", timeout=15000)
        page.wait_for_timeout(500)
        save(page, "03_uploaded_identity_doc.png")

        # 4) Successful pipeline run
        page.select_option("#docType", "aadhaar")
        page.select_option("#country", "IN")
        page.select_option("#appType", "passport")
        page.click("#runBtn")

        page.wait_for_selector("#progSection.show", timeout=10000)
        page.wait_for_timeout(800)
        save(page, "04_pipeline_running.png")

        page.wait_for_selector("#resultsSection.show", timeout=45000)
        page.wait_for_timeout(1200)
        page.evaluate(
            "document.getElementById('resultsSection').scrollIntoView({behavior:'instant', block:'start'})"
        )
        page.wait_for_timeout(700)
        save(page, "05_results_success_flow.png")

        # 5) Compliance dashboard snapshot
        page.evaluate(
            "document.getElementById('compliance').scrollIntoView({behavior:'instant', block:'start'})"
        )
        page.wait_for_timeout(1000)
        save(page, "06_compliance_dashboard.png")

        # 6) Case study benchmark
        page.click("button.case-btn")
        page.wait_for_function(
            "() => document.getElementById('caseStudyNote') && document.getElementById('caseStudyNote').textContent.includes('Case Study:')",
            timeout=45000,
        )
        page.wait_for_timeout(600)
        save(page, "07_case_study_benchmark.png")

        # 7) HITL review flow (ineligible path)
        page.evaluate(
            "document.getElementById('demo').scrollIntoView({behavior:'instant', block:'start'})"
        )
        page.wait_for_timeout(900)
        page.select_option("#docType", "aadhaar")
        page.select_option("#country", "US")
        page.select_option("#appType", "visa")
        page.click("#runBtn")

        page.wait_for_selector("#hitlOverlay.show", timeout=45000)
        page.wait_for_timeout(500)
        save(page, "08_hitl_review_modal.png")

        page.click(".btn-approve")
        page.wait_for_selector("#resultsSection.show", timeout=45000)
        page.wait_for_timeout(1200)
        page.evaluate(
            "document.getElementById('resultsSection').scrollIntoView({behavior:'instant', block:'start'})"
        )
        page.wait_for_timeout(700)
        save(page, "09_post_hitl_completion.png")

        # 8) API docs
        docs = context.new_page()
        docs.goto(f"{BASE_URL}/docs", wait_until="networkidle")
        docs.wait_for_timeout(900)
        save(docs, "10_api_docs.png")

        docs.close()
        page.close()
        context.close()
        browser.close()


if __name__ == "__main__":
    try:
        run()
    except PlaywrightTimeoutError as exc:
        raise SystemExit(f"Screenshot capture timed out: {exc}")
