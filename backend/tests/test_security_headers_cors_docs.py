import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app

async def asgi_request(app, method, path, headers=None):
    raw_headers = []
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))
    
    status_code = None
    response_headers = []
    body_chunks = []
    
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
        
    async def send(message):
        nonlocal status_code, response_headers, body_chunks
        if message["type"] == "http.response.start":
            status_code = message["status"]
            response_headers = [(k.decode("latin-1"), v.decode("latin-1")) for k, v in message["headers"]]
        elif message["type"] == "http.response.body":
            body_chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    header_dict = {k.lower(): v for k, v in response_headers}
    body = b"".join(body_chunks)
    return status_code, header_dict, body

async def main():
    print("=== STARTING MAIN SECURITY VERIFICATION (SEC-03, SEC-05, SEC-06, SEC-07) ===")

    # -------------------------------------------------------------
    # SEC-03: CORS Wildcard with Credentials
    # -------------------------------------------------------------
    print("\n[SEC-03] Testing CORS with malicious Origin (https://evil-attacker.example)...")
    status, headers, _ = await asgi_request(
        app,
        "OPTIONS",
        "/health",
        headers={
            "Origin": "https://evil-attacker.example",
            "Access-Control-Request-Method": "GET"
        }
    )
    evil_acao = headers.get("access-control-allow-origin")
    print(f"Malicious Origin response status: {status}")
    print(f"Malicious Origin access-control-allow-origin header: {evil_acao}")
    assert evil_acao is None or evil_acao != "https://evil-attacker.example", "CORS reflected attacker origin!"
    print("PASS: Malicious origin is rejected (no matching Access-Control-Allow-Origin).")

    print("\n[SEC-03] Testing CORS with legitimate Origin (https://ai7finance.alifihsan.my.id)...")
    status, headers, _ = await asgi_request(
        app,
        "OPTIONS",
        "/health",
        headers={
            "Origin": "https://ai7finance.alifihsan.my.id",
            "Access-Control-Request-Method": "GET"
        }
    )
    legit_acao = headers.get("access-control-allow-origin")
    print(f"Legitimate Origin response status: {status}")
    print(f"Legitimate Origin access-control-allow-origin header: {legit_acao}")
    assert legit_acao == "https://ai7finance.alifihsan.my.id", "Legitimate origin was not allowed!"
    print("PASS: Legitimate production origin allowed correctly.")

    print("\n[SEC-03] Testing CORS with legitimate Origin (https://tillfold.alifihsan.my.id)...")
    status, headers, _ = await asgi_request(
        app,
        "OPTIONS",
        "/health",
        headers={
            "Origin": "https://tillfold.alifihsan.my.id",
            "Access-Control-Request-Method": "GET"
        }
    )
    tillfold_acao = headers.get("access-control-allow-origin")
    print(f"Tillfold Origin response status: {status}")
    print(f"Tillfold Origin access-control-allow-origin header: {tillfold_acao}")
    assert tillfold_acao == "https://tillfold.alifihsan.my.id", "Tillfold origin was not allowed!"
    print("PASS: Tillfold production origin allowed correctly.")

    # -------------------------------------------------------------
    # SEC-05: Missing Security Headers
    # -------------------------------------------------------------
    print("\n[SEC-05] Testing Security Headers injection...")
    status, headers, _ = await asgi_request(app, "GET", "/health")
    assert status == 200
    
    expected_headers = {
        "x-content-type-options": "nosniff",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "camera=(), microphone=(), geolocation=()",
        "strict-transport-security": "max-age=31536000; includeSubDomains",
    }
    
    for h, val in expected_headers.items():
        actual = headers.get(h)
        print(f"Header '{h}': {actual}")
        assert actual == val, f"Header {h} mismatch: expected {val}, got {actual}"
    
    assert "x-frame-options" not in headers, "X-Frame-Options must not be set (superseded by frame-ancestors for Telegram Mini App)"
    
    csp = headers.get("content-security-policy")
    print(f"Header 'content-security-policy': {csp}")
    assert csp is not None and "default-src 'self'" in csp, "CSP header missing or incomplete!"
    assert "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org;" in csp, "frame-ancestors for Telegram Mini App missing from CSP!"
    assert "https://ai7finance.alifihsan.my.id" in csp, "ai7finance origin missing from connect-src!"
    assert "https://tillfold.alifihsan.my.id" in csp, "tillfold origin missing from connect-src!"
    print("PASS: All required security headers successfully present.")

    # -------------------------------------------------------------
    # SEC-06: Docs & OpenAPI Disabled in Production
    # -------------------------------------------------------------
    print("\n[SEC-06] Testing Swagger UI, ReDoc, and OpenAPI endpoints...")
    status, _, _ = await asgi_request(app, "GET", "/docs")
    print(f"GET /docs: status={status}")
    assert status == 404, f"Expected 404 for /docs, got {status}"

    status, _, _ = await asgi_request(app, "GET", "/redoc")
    print(f"GET /redoc: status={status}")
    assert status == 404, f"Expected 404 for /redoc, got {status}"

    status, _, _ = await asgi_request(app, "GET", "/api/v1/openapi.json")
    print(f"GET /api/v1/openapi.json: status={status}")
    assert status == 404, f"Expected 404 for /api/v1/openapi.json, got {status}"
    print("PASS: API documentation endpoints return 404 in production environment.")

    # -------------------------------------------------------------
    # SEC-07: Soft-404 Fallthrough on Non-existent API routes
    # -------------------------------------------------------------
    print("\n[SEC-07] Testing Soft-404 on nonexistent API route...")
    status, headers, body = await asgi_request(app, "GET", "/api/v1/nonexistent")
    print(f"GET /api/v1/nonexistent: status={status}, content-type={headers.get('content-type')}")
    assert status == 404, f"Expected 404, got {status}"
    assert "application/json" in headers.get("content-type", ""), "Expected application/json response!"
    body_json = json.loads(body.decode("utf-8"))
    assert body_json.get("detail") == "Not Found", f"Expected detail='Not Found', got {body_json}"
    print("PASS: Non-existent API route returns 404 JSON (no soft-404 HTML fallthrough).")

    print("\n=== ALL MAIN SECURITY TESTS (SEC-03, SEC-05, SEC-06, SEC-07) PASSED SUCCESSFULLY ===")

def test_security_headers_cors_docs():
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
