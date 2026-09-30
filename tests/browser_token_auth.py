"""Cross-origin browser regression; proxy only to a disposable LOCAL backend.

Start tests/browser_server.py first. Never calls the production services.
All Cookie and Set-Cookie headers are discarded to emulate blocked cookies.
"""
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

BACKEND = os.environ.get("INTEGRA_TEST_URL", "http://127.0.0.1:8081")
FRONTEND = "https://552-blue.vercel.app"
API = "https://five52-9ftx.onrender.com"

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    context = browser.new_context(service_workers="block")
    errors, requests = [], []

    def proxy(route):
        request = route.request
        url = urlsplit(request.url)
        assert f"{url.scheme}://{url.netloc}" in (FRONTEND, API), request.url
        headers = {k: v for k, v in request.all_headers().items() if k not in ("cookie", "host")}
        if url.path.startswith("/api/"):
            assert request.url.startswith(API), request.url
            requests.append((url.path, headers.get("authorization")))
        response = context.request.fetch(BACKEND + url.path + ("?" + url.query if url.query else ""), method=request.method, headers=headers, data=request.post_data_buffer, timeout=60000)
        response_headers = {k: v for k, v in response.headers.items() if k not in ("set-cookie", "content-length", "content-encoding")}
        route.fulfill(status=response.status, headers=response_headers, body=response.body())

    context.route("**/*", proxy)
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(FRONTEND + "/#encounters")
    page.locator("#demo-access").click()
    page.locator("#new-record").wait_for()
    token = page.evaluate("sessionStorage.getItem(AUTH_STORAGE)")
    assert token
    page.reload()
    page.locator("#new-record").wait_for()
    assert page.evaluate("sessionStorage.getItem(AUTH_STORAGE)") == token
    page.evaluate("location.hash='patients'")
    page.locator(".patient-open").first.click()
    expect(page.get_by_role("heading", name="Prontuário municipal", exact=True)).to_be_visible()
    page.locator("#close-modal").click()
    page.evaluate("location.hash='encounters'")
    page.locator("#new-record").wait_for()
    with page.expect_download() as download:
        page.get_by_role("link", name="Exportar CSV").click()
    assert download.value.suggested_filename.endswith(".csv")

    # A transient API failure must preserve authentication.
    page.evaluate("""async()=>{const original=window.fetch;window.fetch=async()=>new Response('{}',{status:503});try{await api('/meta');}catch(error){}finally{window.fetch=original;}}""")
    assert page.evaluate("authToken") == token
    assert page.evaluate("state.user!==null")
    # A delayed unauthorized response from a previous login cannot clear a new token.
    page.evaluate("""async()=>{const original=window.fetch;let release;window.fetch=()=>new Promise(resolve=>release=()=>resolve(new Response('{}',{status:401})));const pending=api('/meta').catch(()=>{});saveToken('new-session');release();await pending;window.fetch=original;}""")
    assert page.evaluate("authToken") == "new-session"
    page.evaluate("token=>saveToken(token)", token)
    page.locator("#user-menu").click()
    page.locator("#logout").click()
    expect(page.locator("#login-form")).to_be_visible()
    assert page.evaluate("sessionStorage.getItem(AUTH_STORAGE)") is None
    assert context.request.get(BACKEND + "/api/meta", headers={"Authorization": "Bearer " + token}).status == 401

    page.get_by_role("button", name="Sou cidadão", exact=True).click()
    page.locator("#demo-access").click()
    expect(page.get_by_role("heading", name="Olá, Maria.")).to_be_visible()
    assert page.evaluate("""async()=>{for(let i=0;i<450;i++){if(citizenRevision)return true;await new Promise(resolve=>setTimeout(resolve,100));}return false;}"""), "SSE did not deliver a revision"
    assert any(path == "/api/citizen/events" and bearer for path, bearer in requests)
    page.reload()
    expect(page.get_by_role("heading", name="Olá, Maria.")).to_be_visible()
    citizen_token = page.evaluate("authToken")
    page.locator("#citizen-logout").click()
    expect(page.locator("#login-form")).to_be_visible()
    page.evaluate("token=>saveToken(token)", citizen_token)
    page.reload()
    expect(page.locator("#login-form")).to_be_visible()
    assert page.evaluate("sessionStorage.getItem(AUTH_STORAGE)") is None
    assert not context.cookies()
    assert all(bearer and bearer.startswith("Bearer ") for path, bearer in requests if path not in ("/api/login", "/api/session"))
    assert not errors, errors
    # Logout/reload aborts SSE while the local proxy is still buffering its body.
    context.unroute_all(behavior="ignoreErrors")
    browser.close()
    print("OK: cross-origin sem cookies; login, reload #encounters, prontuário, CSV, SSE, falha transitória e logout revogado.")
