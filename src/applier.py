"""Assisted apply.

For each approved job it opens the posting in a real (headed) browser, tries to
pre-fill the obvious fields (name, email, phone) and attach your resume, then
hands control to YOU to review and click Submit. Nothing is submitted
automatically — you stay in control, one job at a time.

A persistent browser profile is kept in data/.browser so logins to a given ATS
(Workday, Greenhouse, LinkedIn, …) survive between runs — you sign in once.

Requires Playwright + a browser:
    .venv/Scripts/python.exe -m pip install playwright
    .venv/Scripts/python.exe -m playwright install chromium
"""
from __future__ import annotations

import re

from . import config, resume_parser, tracker

PROFILE_DIR = config.DATA_DIR / ".browser"

# input hints -> value, matched loosely against name/id/placeholder/aria-label
def _field_map() -> dict[str, str]:
    c = config.applicant_contact()
    return {
        "first name": c["full_name"].split(" ")[0] if c["full_name"] else "",
        "last name": c["full_name"].split(" ")[-1] if c["full_name"] else "",
        "full name": c["full_name"],
        "name": c["full_name"],
        "email": c["email"],
        "phone": c["phone"],
        "mobile": c["phone"],
        "linkedin": c["linkedin"],
        "portfolio": c["portfolio"],
        "github": c["github"],
        "website": c["portfolio"],
    }


def _prefill(page, resume_path) -> int:
    """Best-effort fill of visible text inputs + resume upload. Returns #fields filled."""
    fields = _field_map()
    filled = 0
    for hint, value in fields.items():
        if not value:
            continue
        # match common attributes containing the hint
        selector = ", ".join(
            f'input[{a}*="{hint}" i]:visible' for a in ("name", "id", "placeholder", "aria-label")
        )
        try:
            el = page.locator(selector).first
            if el.count() and not (el.input_value() or "").strip():
                el.fill(value, timeout=1500)
                filled += 1
        except Exception:  # noqa: BLE001 - forms vary wildly; skip what doesn't fit
            continue

    # attach resume to the first file input, if any
    if resume_path:
        try:
            file_input = page.locator('input[type="file"]').first
            if file_input.count():
                file_input.set_input_files(str(resume_path))
                filled += 1
        except Exception:  # noqa: BLE001
            pass
    return filled


_SUBMIT_HINTS = ("submit application", "submit", "apply now", "easy apply", "send application")


def attempt_submit(page) -> bool:
    """Best-effort click of a submit/apply button. Returns True if one was clicked.
    Only call when the user has opted into auto-submit — many ATS need extra steps."""
    for hint in _SUBMIT_HINTS:
        try:
            btn = page.get_by_role("button", name=re.compile(hint, re.I)).first
            if btn.count():
                btn.click(timeout=3000)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def open_and_fill(page, url: str, resume, auto_submit: bool = False) -> str:
    """Open a job, pre-fill it, optionally attempt submit. Returns a status string."""
    page.goto(url, timeout=45000)
    page.wait_for_timeout(2500)
    n = _prefill(page, resume)
    if auto_submit:
        return "submitted" if attempt_submit(page) else f"filled {n} field(s); submit not found — review in browser"
    return f"filled {n} field(s) — review & submit in the browser window"


def run() -> None:
    queue = tracker.approved_pending()
    if not queue:
        print("No approved jobs to apply to. Approve some first: "
              "`python -m src.main approve <row#>`")
        return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "Playwright not installed. Run:\n"
            "  .venv/Scripts/python.exe -m pip install playwright\n"
            "  .venv/Scripts/python.exe -m playwright install chromium"
        )

    resume = resume_parser.find_resume()
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Assisted apply for {len(queue)} approved job(s). "
          "Review each, then click Submit yourself.\n")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False, viewport={"width": 1280, "height": 900},
        )
        for job in queue:
            url = job["url"]
            print(f"→ {job['company']} — {job['title']}\n  {url}")
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(url, timeout=45000)
                page.wait_for_timeout(2500)
                n = _prefill(page, resume)
                tracker.mark_apply_state(url, "assisted_opened")
                print(f"  pre-filled {n} field(s). Review the form, complete any "
                      "remaining questions, and submit.")
            except Exception as exc:  # noqa: BLE001
                tracker.mark_apply_state(url, "failed")
                print(f"  could not open/prefill ({exc}). Opening URL for manual apply.")

            ans = input("  Did you submit this application? [y=submitted / s=skip / q=quit]: ").strip().lower()
            if ans == "y":
                tracker.mark_apply_state(url, "submitted")
                print("  marked as submitted.\n")
            elif ans == "q":
                print("  stopping.")
                break
            else:
                print("  left as pending.\n")
        ctx.close()
