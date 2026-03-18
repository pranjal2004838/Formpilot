"""Agent 5: Discover, fill, and safely submit live web forms with Playwright."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from agents.base import Agent, AgentInput, AgentOutput
from utils.form_mapping import normalize_text


class BrowserSubmissionAgent(Agent):
    def __init__(self, artifact_root: Optional[Path] = None) -> None:
        super().__init__(name="BrowserSubmitter")
        self.artifact_root = artifact_root or Path(__file__).resolve().parents[2] / "assets" / "browser-runs"

    @property
    def available(self) -> bool:
        try:
            import playwright.async_api  # noqa: F401
        except Exception:
            return False
        return True

    async def discover_form_fields(
        self,
        target_url: str,
        *,
        headless: bool = True,
        timeout_ms: int = 30000,
    ) -> Dict[str, Any]:
        async with self._browser_context(headless=headless) as page:
            await self._goto(page, target_url, timeout_ms=timeout_ms)
            snapshot = await self._page_snapshot(page)
            primary_form = self._select_primary_form(snapshot.get("forms", []))
            if not primary_form:
                raise RuntimeError(f"No fillable form detected at {target_url}")

            blockers = self._detect_blockers(snapshot, primary_form)
            policy = self._submission_policy(page.url, primary_form, blockers, submit_requested=True)

            return {
                "target_url": target_url,
                "resolved_url": page.url,
                "form": {
                    "action": primary_form.get("action"),
                    "method": primary_form.get("method"),
                    "control_count": len(primary_form.get("controls", [])),
                },
                "fields": self._fillable_fields(primary_form),
                "blockers": blockers,
                "policy": policy,
            }

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        config = input_data.metadata.get("browser_automation") or {}
        target_url = str(config.get("target_url") or "").strip()
        if not target_url:
            return AgentOutput(status="error", data={}, errors=["Missing browser_automation.target_url"])

        mappings = list(input_data.metadata.get("mappings") or [])
        extra_values = config.get("extra_values") or {}
        submit_requested = bool(config.get("submit", True))
        headless = bool(config.get("headless", True))
        timeout_ms = int(config.get("timeout_ms", 30000))
        allow_hitl = bool(config.get("allow_hitl", True))  # Enable HITL mode by default
        workflow_id = input_data.workflow_id or "browser-run"

        for key, value in extra_values.items():
            mappings.append(
                {
                    "formField": key,
                    "profileField": "extra_values",
                    "value": str(value),
                    "transformation": "none",
                    "confidence": 1.0,
                }
            )

        artifact_dir = self.artifact_root / workflow_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        try:
            async with self._browser_context(headless=headless) as page:
                await self._goto(page, target_url, timeout_ms=timeout_ms)
                snapshot = await self._page_snapshot(page)
                primary_form = self._select_primary_form(snapshot.get("forms", []))
                if not primary_form:
                    raise RuntimeError(f"No fillable form detected at {target_url}")

                blockers = self._detect_blockers(snapshot, primary_form)
                policy = self._submission_policy(page.url, primary_form, blockers, submit_requested=submit_requested)
                fields = self._fillable_fields(primary_form)

                before_fill = artifact_dir / "before_fill.png"
                await page.screenshot(path=str(before_fill), full_page=True)

                matched_fields, skipped_fields = await self._fill_fields(page, fields, mappings)
                if submit_requested and not matched_fields:
                    raise RuntimeError("Browser submission blocked: no mapped fields could be applied to the live form.")

                after_fill = artifact_dir / "after_fill.png"
                await page.screenshot(path=str(after_fill), full_page=True)

                # ===== NEW: HITL (Human-In-The-Loop) Mode =====
                # If blockers detected and user requested submission, pause and ask for human help
                if submit_requested and blockers and allow_hitl:
                    import uuid
                    from datetime import datetime
                    
                    session_id = str(uuid.uuid4())
                    interaction_type = self._classify_blocker(blockers)
                    prompt = self._generate_hitl_prompt(interaction_type, blockers)
                    
                    # Save state for resume
                    state_file = artifact_dir / "hitl_state.json"
                    import json
                    try:
                        filled_values = {
                            f.get("name") or f.get("id"): m.get("value")
                            for f in fields
                            for m in mappings
                            if m.get("formField") == (f.get("name") or f.get("id"))
                        }
                    except:
                        filled_values = {}
                    
                    hitl_state = {
                        "session_id": session_id,
                        "workflow_id": workflow_id,
                        "target_url": target_url,
                        "resolved_url": page.url,
                        "blockers": blockers,
                        "interaction_type": interaction_type,
                        "filled_values": filled_values,
                        "form_snapshot": primary_form,
                        "paused_at": datetime.now().isoformat(),
                    }
                    with open(state_file, "w") as f:
                        json.dump(hitl_state, f, indent=2, default=str)
                    
                    # Return HITL response
                    data = {
                        "target_url": target_url,
                        "resolved_url": page.url,
                        "needs_human_interaction": True,
                        "interaction_type": interaction_type,
                        "interaction_prompt": prompt,
                        "interaction_session_id": session_id,
                        "paused_at": datetime.now().isoformat(),
                        "matched_fields": matched_fields,
                        "skipped_fields": skipped_fields,
                        "filled_values": filled_values,
                        "form_snapshot": primary_form,
                        "blockers_detected": blockers,
                        "screenshots": [str(before_fill), str(after_fill)],
                        "policy": policy,
                    }
                    return AgentOutput(
                        status="awaiting_user_interaction",
                        data=data,
                        confidence=0.8,
                    )
                # ===== END HITL Mode =====

                submitted = False
                submit_reason = "Dry run only."
                after_submit_path = None

                if submit_requested:
                    if not policy["submit_allowed"]:
                        raise RuntimeError("Browser submission blocked: " + "; ".join(policy["reasons"]))

                    button_text = await self._submit_form(page, primary_form)
                    submitted = True
                    submit_reason = f"Submitted via {button_text or 'form submit action'}."
                    after_submit_path = artifact_dir / "after_submit.png"
                    await page.screenshot(path=str(after_submit_path), full_page=True)

                confidence = len(matched_fields) / max(len(mappings), 1)
                data = {
                    "target_url": target_url,
                    "resolved_url": page.url,
                    "submitted": submitted,
                    "message": submit_reason,
                    "needs_human_interaction": False,
                    "policy": policy,
                    "blockers": blockers,
                    "matched_fields": matched_fields,
                    "skipped_fields": skipped_fields,
                    "form": {
                        "action": primary_form.get("action"),
                        "method": primary_form.get("method"),
                        "control_count": len(primary_form.get("controls", [])),
                    },
                    "screenshots": [
                        str(before_fill),
                        str(after_fill),
                        *( [str(after_submit_path)] if after_submit_path else [] ),
                    ],
                }
                return AgentOutput(status="success", data=data, confidence=confidence)
        except Exception as exc:
            return AgentOutput(status="error", data={}, confidence=0, errors=[str(exc)])

    async def _fill_fields(
        self,
        page: Any,
        fields: List[Dict[str, Any]],
        mappings: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        matched_fields: List[Dict[str, Any]] = []
        skipped_fields: List[Dict[str, Any]] = []
        used_keys = set()

        for mapping in mappings:
            target = str(mapping.get("formField") or "").strip()
            value = str(mapping.get("value") or "").strip()
            if not target or not value:
                continue

            field = self._match_field(target, fields, used_keys)
            if not field:
                skipped_fields.append({"formField": target, "reason": "No matching control found"})
                continue

            locator = self._locator_for_field(page, field)
            if locator is None:
                skipped_fields.append({"formField": target, "reason": "Unable to build locator"})
                continue

            try:
                await self._apply_value(locator, field, value)
            except Exception as exc:
                skipped_fields.append({"formField": target, "reason": str(exc)})
                continue
            field_key = field.get("name") or field.get("id") or field.get("label") or target
            used_keys.add(field_key)
            matched_fields.append(
                {
                    "formField": target,
                    "control": field_key,
                    "value": value,
                    "controlType": field.get("type") or field.get("tagName"),
                }
            )

        return matched_fields, skipped_fields

    async def _submit_form(self, page: Any, primary_form: Dict[str, Any]) -> str:
        submit_candidates = [
            control
            for control in primary_form.get("controls", [])
            if control.get("tagName") == "button" or control.get("type") in {"submit", "image"}
        ]
        if submit_candidates:
            button = submit_candidates[0]
            locator = self._locator_for_field(page, button)
            if locator is not None:
                await locator.click()
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                return button.get("label") or button.get("value") or "submit"

        form_index = int(primary_form.get("index", 0))
        await page.locator("form").nth(form_index).evaluate("form => form.requestSubmit ? form.requestSubmit() : form.submit()")
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        return "requestSubmit"

    async def _apply_value(self, locator: Any, field: Dict[str, Any], value: str) -> None:
        tag_name = (field.get("tagName") or "").lower()
        field_type = (field.get("type") or "text").lower()

        if tag_name == "select":
            options = field.get("options", []) or []
            best_value = self._matching_option_value(options, value)
            if best_value is None:
                raise RuntimeError(f"No matching option for field {field.get('name') or field.get('id')} value {value!r}")
            await locator.select_option(best_value)
            return

        if field_type == "checkbox":
            normalized = normalize_text(value)
            if normalized in {"true", "yes", "1", "checked", "on"}:
                await locator.check()
            else:
                await locator.uncheck()
            return

        if field_type == "radio":
            await locator.check()
            return

        await locator.fill(value)

    def _matching_option_value(self, options: List[Dict[str, Any]], value: str) -> Optional[str]:
        normalized_value = normalize_text(value)
        best_option = None
        best_score = 0
        for option in options:
            label = normalize_text(option.get("label") or option.get("text") or option.get("value"))
            if not label:
                continue
            score = 100 if label == normalized_value else 0
            if normalized_value and score == 0:
                score = max(score, len(set(label.split()) & set(normalized_value.split())) * 25)
            if score > best_score:
                best_score = score
                best_option = option.get("value")
        if best_option is not None:
            return str(best_option)
        return None

    def _match_field(
        self,
        target: str,
        fields: List[Dict[str, Any]],
        used_keys: set,
    ) -> Optional[Dict[str, Any]]:
        target_norm = normalize_text(target)
        best_field = None
        best_score = 0
        for field in fields:
            field_key = field.get("name") or field.get("id") or field.get("label")
            if field_key in used_keys:
                continue

            candidates = [
                normalize_text(field.get("name")),
                normalize_text(field.get("id")),
                normalize_text(field.get("label")),
                normalize_text(field.get("placeholder")),
                normalize_text(field.get("ariaLabel")),
            ]
            score = 0
            for candidate in candidates:
                if not candidate:
                    continue
                if candidate == target_norm:
                    score = max(score, 100)
                elif target_norm in candidate or candidate in target_norm:
                    score = max(score, 90)
                else:
                    score = max(score, 60 if len(set(candidate.split()) & set(target_norm.split())) else 0)
            if score > best_score:
                best_score = score
                best_field = field
        return best_field if best_score >= 60 else None

    def _fillable_fields(self, primary_form: Dict[str, Any]) -> List[Dict[str, Any]]:
        fields: List[Dict[str, Any]] = []
        for control in primary_form.get("controls", []):
            if not control.get("visible") or control.get("disabled"):
                continue
            if control.get("tagName") == "button":
                continue
            if control.get("type") in {"hidden", "submit", "button", "reset", "image", "file"}:
                continue
            fields.append(control)
        return fields

    def _select_primary_form(self, forms: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not forms:
            return None
        ranked = sorted(forms, key=lambda item: sum(1 for c in item.get("controls", []) if c.get("visible")), reverse=True)
        return ranked[0]

    def _submission_policy(
        self,
        resolved_url: str,
        primary_form: Dict[str, Any],
        blockers: List[str],
        *,
        submit_requested: bool,
    ) -> Dict[str, Any]:
        host = (urlparse(resolved_url).hostname or "").lower()
        method = str(primary_form.get("method") or "get").lower()
        is_government = host.endswith(".gov.in") or host.endswith(".nic.in") or host == "services.india.gov.in"
        reasons: List[str] = []

        if blockers:
            reasons.extend(blockers)
        if is_government and method != "get":
            reasons.append("Live government form submission is blocked unless the target uses a safe GET workflow.")

        return {
            "target_host": host,
            "government_domain": is_government,
            "method": method,
            "submit_requested": submit_requested,
            "submit_allowed": submit_requested and not reasons,
            "reasons": reasons,
        }

    def _detect_blockers(self, snapshot: Dict[str, Any], primary_form: Dict[str, Any]) -> List[str]:
        blockers: List[str] = []
        page_text = normalize_text(snapshot.get("pageText", ""))
        form_text = normalize_text(primary_form.get("text", ""))
        if any(token in page_text for token in ("captcha", "recaptcha", "i am not a robot")):
            blockers.append("CAPTCHA detected on target page.")
        if any(token in form_text for token in ("sign in", "login", "log in", "one time password", "otp")):
            blockers.append("Authentication or OTP flow detected on target page.")

        for control in primary_form.get("controls", []):
            field_type = (control.get("type") or "").lower()
            field_name = normalize_text(control.get("name") or control.get("id") or control.get("label"))
            if field_type == "password":
                blockers.append("Password field detected on target form.")
                break
            if "captcha" in field_name or "otp" in field_name:
                blockers.append("CAPTCHA or OTP control detected on target form.")
                break
        return blockers

    def _locator_for_field(self, page: Any, field: Dict[str, Any]) -> Any:
        field_id = field.get("id")
        field_name = field.get("name")
        tag_name = (field.get("tagName") or "input").lower()
        field_type = (field.get("type") or "").lower()

        if tag_name == "button":
            if field_id:
                return page.locator(f"#{field_id}").first
            if field_name:
                return page.locator(f"button[name='{field_name}']").first
            label = field.get("label") or field.get("value")
            if label:
                return page.get_by_role("button", name=label).first
            return page.locator("button[type='submit']").first

        if field_id:
            return page.locator(f"#{field_id}").first
        if field_name and field_type == "radio":
            value = field.get("value")
            if value is not None:
                return page.locator(f"input[type='radio'][name='{field_name}'][value='{value}']").first
        if field_name:
            selector = f"{tag_name}[name='{field_name}']" if tag_name != "input" else f"[name='{field_name}']"
            return page.locator(selector).first
        return None

    async def _goto(self, page: Any, target_url: str, *, timeout_ms: int) -> None:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

    async def _page_snapshot(self, page: Any) -> Dict[str, Any]:
        return await page.evaluate(
            """
            () => {
              const visible = (el) => {
                const style = window.getComputedStyle(el);
                return style && style.visibility !== 'hidden' && style.display !== 'none' && !el.disabled;
              };
              const labelFor = (el) => {
                if (el.id) {
                  const linked = document.querySelector(`label[for="${el.id}"]`);
                  if (linked) return linked.innerText.trim();
                }
                const parent = el.closest('label');
                if (parent) return parent.innerText.trim();
                return el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
              };
              const controls = (form) => Array.from(form.querySelectorAll('input, select, textarea, button')).map((el) => {
                const tagName = el.tagName.toLowerCase();
                const options = tagName === 'select'
                  ? Array.from(el.options || []).map((option) => ({ value: option.value, label: option.textContent.trim() }))
                  : [];
                return {
                  tagName,
                  type: (el.getAttribute('type') || '').toLowerCase(),
                  name: el.getAttribute('name') || '',
                  id: el.getAttribute('id') || '',
                  value: el.getAttribute('value') || '',
                  label: labelFor(el),
                  placeholder: el.getAttribute('placeholder') || '',
                  ariaLabel: el.getAttribute('aria-label') || '',
                  required: el.required || false,
                  disabled: el.disabled || false,
                  visible: visible(el),
                  checked: !!el.checked,
                  options,
                  text: (el.innerText || '').trim(),
                };
              });
              return {
                title: document.title,
                pageText: document.body ? document.body.innerText : '',
                forms: Array.from(document.querySelectorAll('form')).map((form, index) => ({
                  index,
                  action: form.action || window.location.href,
                  method: (form.method || 'get').toLowerCase(),
                                    text: (form.innerText || '').trim(),
                  controls: controls(form),
                })),
              };
            }
            """
        )

    @asynccontextmanager
    async def _browser_context(self, *, headless: bool):
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            page = await browser.new_page()
            try:
                yield page
            finally:
                await browser.close()

    def _classify_blocker(self, blockers: List[str]) -> str:
        """Classify the primary blocker type from detected blockers."""
        text = " ".join(blockers).lower()
        if "captcha" in text:
            return "solve_captcha"
        if "otp" in text:
            return "enter_otp"
        if "password" in text or "authentication" in text or "login" in text:
            return "solve_password_gate"
        return "solve_security_challenge"

    def _generate_hitl_prompt(self, interaction_type: str, blockers: List[str]) -> str:
        """Generate human-readable prompt for user interaction."""
        prompts = {
            "solve_captcha": 
                "🔒 CAPTCHA detected: The form requires you to solve a CAPTCHA challenge. "
                "Please solve it in the browser window, and we'll resume submission once you confirm. "
                "Blockers: " + "; ".join(blockers),
            "enter_otp": 
                "📱 OTP Authentication required: The form expects a One-Time Password or Multi-Factor Authentication. "
                "Please complete the OTP verification in the browser, and we'll resume submission when ready. "
                "Blockers: " + "; ".join(blockers),
            "solve_password_gate": 
                "🔐 Authentication gate detected: The form or protected resource requires login/password. "
                "Please authenticate using the login form, and we'll resume submission afterward. "
                "Blockers: " + "; ".join(blockers),
            "solve_security_challenge": 
                "🛡️ Security challenge detected: The form has security requirements before submission. "
                "Please complete the security challenge, and we'll resume submission when ready. "
                "Blockers: " + "; ".join(blockers),
        }
        return prompts.get(interaction_type, prompts["solve_security_challenge"])