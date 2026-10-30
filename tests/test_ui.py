"""Browser-level checks use the system Chromium; no browser download is required."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

chromium = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
pytestmark = pytest.mark.skipif(not chromium, reason="System Chromium is not installed")


def test_real_visual_editor_and_worksheet_flow(tmp_path):
    from playwright.sync_api import expect, sync_playwright

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "XDG_DATA_HOME": str(tmp_path / "data")}
    process = subprocess.Popen(
        [sys.executable, "-m", "resolvent", "serve", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(url + "/api/health", timeout=0.2).close()
                break
            except OSError:
                if process.poll() is not None:
                    pytest.fail(process.stderr.read().decode())
                time.sleep(0.1)
        else:
            pytest.fail("The UI server did not become ready")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=chromium, headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page(viewport={"width": 1450, "height": 1080}, device_scale_factor=1)
            errors, external_requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda req: external_requests.append(req.url) if not req.url.startswith(url) else None,
            )
            page.goto(url)
            expect(page.locator(".quick-operation")).to_have_count(5)
            page.locator("#compute-button").click()
            expect(page.locator("#result-status")).to_have_text("COMPUTED", timeout=30000)
            expect(page.locator("#result-json")).to_contain_text("3*x**2 - 3")

            # Python editor and malformed-input feedback.
            page.get_by_role("tab", name="Python", exact=True).click()
            page.locator("#code-input").fill("(1).__class__")
            page.locator("#compute-button").click()
            expect(page.locator("#error-box")).to_be_visible(timeout=30000)
            page.locator("#code-input").fill("sin(x)*exp(x)")
            page.locator("#compute-button").click()
            expect(page.locator("#result-status")).to_have_text("COMPUTED", timeout=30000)
            expect(page.locator("#result-json")).to_contain_text("cos(x)")

            # The actual WYSIWYG editor receives LaTeX and computes a definite integral.
            page.get_by_role("tab", name="LaTeX", exact=True).click()
            page.locator("#code-input").fill(r"\frac{x^2}{2}")
            page.get_by_role("tab", name="Visual", exact=True).click()
            page.get_by_role("button", name="∫ Integrate", exact=True).click()
            page.locator("#param-bounds").fill("[0, 2]")
            page.locator("#compute-button").click()
            expect(page.locator("#result-json")).to_contain_text("4/3", timeout=30000)
            screenshot = os.environ.get("RESOLVENT_SCREENSHOT")
            if screenshot:
                page.locator("#toast").wait_for(state="hidden", timeout=5000)
                page.screenshot(path=screenshot, full_page=True)

            # Plotting generates local SVG curves and resamples when zooming.
            page.locator('[data-preset="plot"]').click()
            page.locator("#compute-button").click()
            expect(page.locator("#plot-container")).to_be_visible(timeout=30000)
            expect(page.locator("#plot-svg path")).to_have_count(2)
            page.locator("#zoom-in").click()
            expect(page.locator("#param-lower")).to_have_value(str(-3.141592653589793))
            expect(page.locator("#compute-button")).to_be_enabled(timeout=30000)

            # Save, export, load, and delete a real persisted worksheet.
            page.locator("#worksheet-title").fill("Calculus notebook")
            page.locator("#save-button").click()
            expect(page.locator("#save-state")).to_have_text("Saved locally")
            with page.expect_download() as downloaded:
                page.locator("#export-button").click()
            exported = tmp_path / "worksheet.json"
            downloaded.value.save_as(exported)
            data = json.loads(exported.read_text())
            assert data["title"] == "Calculus notebook"
            assert len(data["cells"]) == 5
            page.locator("#new-worksheet").click()
            expect(page.locator("#history-list .history-item")).to_have_count(0)
            page.locator("#saved-nav").click()
            page.locator(".saved-entry > button").first.click()
            expect(page.locator("#history-list .history-item")).to_have_count(5)
            expect(page.locator("#worksheet-title")).to_have_value("Calculus notebook")
            page.locator("#saved-nav").click()
            page.get_by_role("button", name="Delete Calculus notebook").click()
            page.locator("#confirm-ok").click()
            expect(page.locator(".saved-entry")).to_have_count(0)
            page.locator("#import-file").set_input_files(exported)
            page.locator("#confirm-ok").click()
            expect(page.locator("#history-list .history-item")).to_have_count(5)

            # The layout remains within the viewport on narrow screens.
            page.set_viewport_size({"width": 700, "height": 900})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            assert not external_requests, external_requests
            browser.close()
    finally:
        process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
