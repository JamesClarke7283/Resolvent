import json
import re
import subprocess
import sys
import threading
import types
import urllib.request

import pytest

from resolvent.models import MathError
from resolvent.service import MathService
from resolvent.web import create_app


def test_desktop_server_lifecycle_keeps_gui_on_main_thread(monkeypatch, tmp_path):
    from resolvent.desktop import launch

    state = {}

    def create_window(title, url, **kwargs):
        state["url"] = url

    def start(**kwargs):
        assert threading.current_thread() is threading.main_thread()
        with urllib.request.urlopen(state["url"] + "/api/health", timeout=3) as response:
            assert json.load(response)["status"] == "ok"

    settings = {}
    monkeypatch.setitem(
        sys.modules,
        "webview",
        types.SimpleNamespace(create_window=create_window, start=start, settings=settings),
    )
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    launch()
    assert settings["ALLOW_DOWNLOADS"] is True
    assert not any(t.name == "resolvent-server" for t in threading.enumerate())


def test_isolated_calculation_and_timeout():
    service = MathService(timeout=15)
    assert (
        service.calculate(
            {"operation": "integrate", "expression": "x**2", "parameters": {"bounds": [0, 1]}}
        ).result
        == "1/3"
    )
    with pytest.raises(MathError) as error:
        MathService(timeout=0.001).calculate({"operation": "factor", "expression": "x**2-1"})
    assert error.value.code == "timeout"
    # The timed-out child is terminated and does not poison a subsequent call.
    assert service.calculate({"operation": "evaluate", "expression": "1+1"}).result == "2"


def test_cli_json_and_failure_exit_code():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "resolvent",
            "calc",
            "integrate",
            "x**2",
            "--param",
            "bounds=[0,1]",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"] == "1/3"
    result = subprocess.run(
        [sys.executable, "-m", "resolvent", "calc", "evaluate", "(1).__class__", "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "error" in json.loads(result.stdout)


@pytest.mark.asyncio
async def test_http_calculate_worksheets_and_session_protection(tmp_path):
    app = create_app(database=tmp_path / "worksheets.sqlite3")
    client = app.test_client()
    response = await client.get("/")
    html = await response.get_data(as_text=True)
    token = re.search(r'name="resolvent-token" content="([^"]+)"', html).group(1)
    headers = {"X-Resolvent-Token": token}
    payload = {"operation": "differentiate", "expression": "x**3"}
    response = await client.post("/api/calculate", json=payload)
    assert response.status_code == 403
    response = await client.post("/api/calculate", json=payload, headers=headers)
    assert response.status_code == 200
    assert (await response.get_json())["result"] == "3*x**2"
    response = await client.post(
        "/api/calculate", json=payload, headers={**headers, "Origin": "https://other.example"}
    )
    assert response.status_code == 403
    response = await client.get("/api/operations", headers={"Host": "untrusted.example"})
    assert response.status_code == 403
    response = await client.post(
        "/api/worksheets", json={"title": "Calculus", "cells": [payload]}, headers=headers
    )
    assert response.status_code == 201
    saved = await response.get_json()
    response = await client.get(f"/api/worksheets/{saved['id']}")
    assert (await response.get_json())["cells"][0]["expression"] == "x**3"
    response = await client.put(
        f"/api/worksheets/{saved['id']}", json={"title": "Renamed", "cells": []}, headers=headers
    )
    assert (await response.get_json())["title"] == "Renamed"
    response = await client.delete(f"/api/worksheets/{saved['id']}", headers=headers)
    assert response.status_code == 204
    assert (await client.get(f"/api/worksheets/{saved['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_mcp_real_stdio_handshake_and_tool_call():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=["-m", "resolvent", "mcp"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {"calculate", "batch_calculate", "list_operations"}
            result = await session.call_tool(
                "calculate",
                {
                    "request": {
                        "operation": "integrate",
                        "expression": r"\frac{x^2}{2}",
                        "syntax": "latex",
                        "parameters": {"bounds": [0, 2]},
                    }
                },
            )
            assert not result.isError, result.content
            assert result.structuredContent["result"] == "4/3"
            bad = await session.call_tool(
                "calculate", {"request": {"operation": "evaluate", "expression": "(1).__class__"}}
            )
            assert bad.isError
            resources = await session.list_resources()
            assert any(str(resource.uri) == "resolvent://operations" for resource in resources.resources)
