"""Loopback-only Quart API and offline web UI."""

import secrets
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError
from quart import Quart, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from resolvent import __version__
from resolvent.catalog import catalog
from resolvent.models import MathError, MathRequest, Worksheet
from resolvent.service import MathService
from resolvent.storage import WorksheetStore


def create_app(*, database: Path | None = None, timeout: float = 15) -> Quart:
    app = Quart(__name__)
    app.config.update(MAX_CONTENT_LENGTH=512 * 1024, SECRET_KEY=secrets.token_hex(32))
    service = MathService(timeout=timeout)
    store = WorksheetStore(database)
    token = secrets.token_urlsafe(32)
    app.extensions["math_service"] = service
    app.extensions["worksheet_store"] = store

    @app.before_request
    async def local_requests():
        # Defend the loopback server against DNS rebinding and cross-site writes.
        host = urlsplit("http://" + request.host).hostname
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return jsonify(error={"code": "forbidden", "message": "Only loopback hosts are accepted."}), 403
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                return jsonify(
                    error={"code": "forbidden", "message": "Cross-origin requests are blocked."}
                ), 403
            if not secrets.compare_digest(request.headers.get("X-Resolvent-Token", ""), token):
                return jsonify(
                    error={"code": "forbidden", "message": "Missing or invalid local session token."}
                ), 403

    @app.after_request
    async def secure_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; img-src 'self' data: blob:; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        if request.path.startswith("/api/") or request.path == "/":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(MathError)
    async def math_error(error):
        status = 408 if error.code == "timeout" else 429 if error.code == "busy" else 400
        return jsonify(error={"code": error.code, "message": str(error)}), status

    @app.errorhandler(ValidationError)
    async def validation_error(error):
        return jsonify(error={"code": "invalid_request", "message": str(error)}), 400

    @app.errorhandler(HTTPException)
    async def http_error(error):
        return jsonify(error={"code": error.name, "message": error.description}), error.code

    @app.get("/")
    async def index():
        return await render_template("index.html", version=__version__, token=token)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/operations")
    async def operations():
        return {"operations": catalog()}

    @app.post("/api/calculate")
    async def calculate():
        payload = await request.get_json()
        result = await service.acalculate(MathRequest.model_validate(payload))
        return result.model_dump()

    @app.get("/api/worksheets")
    async def worksheets():
        return {"worksheets": store.list()}

    @app.get("/api/worksheets/<id>")
    async def worksheet(id):
        result = store.get(id)
        return (
            result
            if result
            else (jsonify(error={"code": "not_found", "message": "Worksheet not found."}), 404)
        )

    @app.post("/api/worksheets")
    async def save_worksheet():
        return store.save(Worksheet.model_validate(await request.get_json())), 201

    @app.put("/api/worksheets/<id>")
    async def update_worksheet(id):
        if not store.get(id):
            return jsonify(error={"code": "not_found", "message": "Worksheet not found."}), 404
        return store.save(Worksheet.model_validate(await request.get_json()), id)

    @app.delete("/api/worksheets/<id>")
    async def delete_worksheet(id):
        if not store.delete(id):
            return jsonify(error={"code": "not_found", "message": "Worksheet not found."}), 404
        return "", 204

    return app
