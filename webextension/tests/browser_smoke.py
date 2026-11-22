"""Opt-in QA: python browser_smoke.py UNPACKED_DIR BROWSER_EXE [--screenshot PATH].
Requires Playwright Python. Traffic to the site is fulfilled by local fixtures.
"""
import argparse
import json
import tempfile
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def exercise(context, screenshot, extension_id=None):
    state = {"business": "compensation", "status": 200, "switched": False, "calls": 0}
    requests = []

    def fixture(route):
        request = route.request
        requests.append((request.method, request.url))
        if request.url.endswith("/api/user/status"):
            state["calls"] += 1
            email = "second" if state["switched"] and state["calls"] % 2 == 0 else "sample"
            route.fulfill(status=state["status"], json={"code": 0, "data": {"email": email + "@example.test"}})
        elif request.url.endswith("/api/user/points"):
            now = int(time.time() * 1000) - 1000
            route.fulfill(json={"points":"37", "history":[
                {"time":now, "business":state["business"], "change":4},
                {"time":now-86400000, "business":"promotion", "change":3},
            ]})
        elif request.url.endswith("/console/checkin"):
            route.fulfill(content_type="text/html", body="<title>Local test fixture</title><h1>Check-in fixture</h1>")
        else:
            route.abort()
    context.route("https://glados.*/**", fixture)
    if not extension_id:
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
        extension_id = worker.url.split("/")[2]
    page = context.pages[0]
    page.goto("chrome-extension://" + extension_id + "/console.html")
    expect(page.locator("#open")).to_be_enabled()
    expect(page.locator("#reminder")).not_to_be_checked()
    assert not requests
    page.locator("#refresh").click()
    expect(page.locator("#feedback")).to_have_text(page.evaluate("chrome.i18n.getMessage('noTab')"))
    with context.expect_page() as created:
        page.locator("#open").click()
    site = created.value
    # Initial navigations initiated by tabs.create can precede Playwright's
    # page interception. Network egress is disabled by the launch proxy.
    site.goto("https://glados.cloud/console/checkin")
    expect(site).to_have_title("Local test fixture")
    expect(page.locator("#refresh")).to_be_enabled()
    page.locator("#open").click()
    expect(page.locator("#refresh")).to_be_enabled()
    assert len([p for p in context.pages if p.url.endswith("/console/checkin")]) == 1
    page.bring_to_front()
    page.locator("#refresh").click()
    expect(page.locator("#points")).to_have_text("37")
    expect(page.locator("#status")).to_have_text(page.evaluate("chrome.i18n.getMessage('unknown')"))
    state["business"] = "system:checkin"
    page.locator("#refresh").click()
    expect(page.locator("#status")).to_have_text(page.evaluate("chrome.i18n.getMessage('confirmed')"))
    expect(page.locator("#account")).to_contain_text("s•••@example.test")
    if screenshot:
        page.screenshot(path=str(screenshot))
    page.set_viewport_size({"width":375,"height":800})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    state["switched"] = True
    state["calls"] = 0
    page.locator("#refresh").click()
    expect(page.locator("#feedback")).to_have_text(page.evaluate("chrome.i18n.getMessage('switched')"))
    expect(page.locator("#points")).to_have_text("—")
    state.update(switched=False, status=401)
    page.locator("#refresh").click()
    expect(page.locator("#feedback")).to_have_text(page.evaluate("chrome.i18n.getMessage('login')"))
    page.locator("#reminder").check()
    expect(page.locator("#open")).to_be_enabled()
    assert page.evaluate("async () => Boolean(await chrome.alarms.get('daily-reminder'))")
    page.reload()
    expect(page.locator("#reminder")).to_be_checked()
    page.locator("#reminder").uncheck()
    expect(page.locator("#open")).to_be_enabled()
    assert not page.evaluate("async () => Boolean(await chrome.alarms.get('daily-reminder'))")
    page.locator("#clear").click()
    expect(page.locator("#noActivity")).to_be_visible()
    assert requests and all(method == "GET" for method, _ in requests), requests
    assert "example.test" not in json.dumps(page.evaluate("chrome.storage.local.get(null)"))
    print("PASS: installation, official tab reuse, ledger evidence, account switch, logout, reminders, privacy, mobile layout.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extension", type=Path)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--cdp-install", action="store_true", help="Load unpacked using the browser's Extensions test API")
    args = parser.parse_args()
    extension = str(args.extension.resolve())
    flags = ["--lang=zh-CN"]
    if args.cdp_install:
        flags.append("--enable-unsafe-extension-debugging")
    else:
        flags.extend(["--disable-extensions-except=" + extension, "--load-extension=" + extension])
    with tempfile.TemporaryDirectory() as profile, sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(profile, executable_path=str(args.executable),
            headless=True, locale="zh-CN", viewport={"width":1250, "height":850},
            proxy={"server":"http://127.0.0.1:9"},
            ignore_default_args=["--disable-extensions"], args=flags)
        try:
            extension_id = None
            if args.cdp_install:
                session = context.browser.new_browser_cdp_session()
                extension_id = session.send("Extensions.loadUnpacked", {"path":extension})["id"]
            exercise(context, args.screenshot, extension_id)
        finally:
            context.close()
