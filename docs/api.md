# Local HTTP API

Run `uv run resolvent serve`. All endpoints are local to this device. GET `/` contains
the `resolvent-token` meta tag. Include this token as `X-Resolvent-Token` for writes.
Tokens change whenever the server restarts. Use the CLI or MCP for non-browser integrations.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Version and status |
| GET | `/api/operations` | Operation metadata and examples |
| POST | `/api/calculate` | A typed mathematical request |
| GET | `/api/worksheets` | Saved worksheet summaries |
| POST | `/api/worksheets` | Save `{title, cells}` |
| GET | `/api/worksheets/<id>` | Retrieve a worksheet |
| PUT | `/api/worksheets/<id>` | Replace a saved worksheet |
| DELETE | `/api/worksheets/<id>` | Remove a saved worksheet |

Example request:

```json
{
  "operation": "differentiate",
  "expression": "sin(x)*exp(x)",
  "syntax": "python",
  "variable": "x",
  "variables": [],
  "parameters": {"order": 2},
  "assumptions": {},
  "precision": 16
}
```

Responses contain `id`, `operation`, normalized `input`, `input_latex`, `result`,
`latex`, optional `numeric`, lossless `data`, `status`, `warnings`, `elapsed_ms`,
and optional `plot` (x samples and y values per curve; gaps are `null`).
Math leaves in `data` are strings. JSON arrays/objects preserve the result structure.

Errors are `{ "error": { "code": "...", "message": "..." } }` with HTTP status 400
for invalid expressions/requests, 403 for rejected local sessions/origins/hosts,
404 for missing worksheets, 408 for calculation timeouts, 413 for oversized bodies,
or 429 when both worker slots are busy.

Writes must be JSON. The maximum body size is 512 KiB; a worksheet supports up to
100 cells and a 120-character title. SQLite is stored per operating-system user.
