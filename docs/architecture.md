# Architecture

```text
MathLive + local Tailwind UI ── Quart HTTP API ─┐
argparse CLI ─────────────────────────────────┼─ MathService ─ worker process ─ SymPy
MCP stdio tools ──────────────────────────────┘                    │
                                                  restricted Python AST / LaTeX parser
```

- `models.py`: the typed request/result and worksheet contracts.
- `catalog.py`: operation descriptions, parameter schemas, and runnable examples.
- `parser.py`: allowlisted mathematical AST interpreter and strict LaTeX parser.
- `engine.py`: symbolic dispatch, exact/LaTeX/structured serialization, plot sampling.
- `service.py`: concurrency limit, subprocess lifecycle, wall/CPU/memory limits.
- `web.py`: local API, session-token validation, security headers, UI routing.
- `storage.py`: SQLite worksheet persistence with parameterized SQL.
- `desktop.py`: Hypercorn event loop in a background thread and pywebview on the main thread.
- `cli.py`: argparse commands and output conventions.
- `mcp_server.py`: official FastMCP tools, resources, and prompt over stdio.
- `templates/` and `static/`: framework-free UI, styles and locally bundled MathLive.

The service always terminates and joins a timed-out worker. The async interfaces
run blocking process supervision in a thread, keeping the Quart/MCP event loop
responsive. Every request is independent; symbolic state does not leak across cells.
Worksheet exports store input requests, not executable Python objects or pickles.

The HTTP server binds to `127.0.0.1`. It checks Host, enforces same-origin writes,
and requires a per-start session token embedded in the index page. No CORS endpoint
or pywebview JavaScript-to-Python bridge is exposed. Dynamic data is inserted with
DOM text nodes or a math-field value, never HTML string interpolation.

To add an operation, define its metadata and example in `catalog.py`, implement its
case in `Evaluation.run()`, then add mathematical assertions to the engine tests.
The example smoke test automatically exercises every advertised operation.
