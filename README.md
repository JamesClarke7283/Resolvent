# Resolvent

A local mathematics workbench for people and language models. Python 3.15, Quart,
pywebview, Tailwind CSS, [MathLive](https://mathlive.io/mathfield/guides/getting-started/),
and SymPy power the same engine in a native desktop window, browser, CLI, and MCP server.

No Node.js or npm is required. The editor, fonts, and compiled styles are bundled;
the running application makes no external network requests.

## Get started

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from this directory:

```bash
uv venv --python 3.15
uv sync --extra desktop
uv run resolvent gui
```

The `.python-version` file pins the project to Python 3.15. `uv` automatically
downloads a suitable interpreter when needed. Dependencies are recorded in `uv.lock`.

For Linux, the Qt renderer is the easiest option inside a uv-managed environment:

```bash
uv sync --extra qt
uv run resolvent gui --gui qt
```

Qt requires a graphical session and the system libraries for Qt WebEngine, including
libGL, libEGL, libxkbcommon, libnss3, and the XCB libraries on X11. GTK can also be used
if PyGObject and WebKitGTK are installed for the same Python interpreter. macOS uses
the native WebKit backend; Windows needs WebView2 Runtime. See
[pywebview's platform prerequisites](https://pywebview.flowrl.com/guide/installation.html).

The browser mode works without a desktop renderer:

```bash
uv sync
uv run resolvent serve --open
# Open http://127.0.0.1:8765 if your browser did not open automatically.
```

The server only binds to loopback. `--port 8766` changes its port. Close the desktop
window or press Ctrl+C in browser mode to stop the server.

## Work in the editor

1. Write an expression in the **Visual** MathLive editor, paste **LaTeX / MathTeX**
   notation, or enter a **Python** mathematical expression.
2. Choose an operation. **Browse all** and the sidebar reveal the complete catalog.
   **Load example** fills in a working input and relevant variables and parameters.
3. Set the variable, optional multivariable list, bounds, assumptions, and precision.
4. Click **Calculate** or press Shift+Enter. Inspect the exact result, numerical
   approximation where available, conditions, and structured data.
5. Save a worksheet locally or export it as JSON. Saved worksheets retain the
   requests; select a cell to recalculate it. Results in session history can be
   copied as text or LaTeX and reused in the editor.

Ctrl/Cmd+S saves; Ctrl/Cmd+N starts a new worksheet. The default database is in the
OS-specific application data directory (`~/.local/share/resolvent/worksheets.sqlite3`
on most Linux installations). A worksheet contains successful calculation requests,
not unexecuted editor drafts. Closing an unsaved worksheet prompts in browser mode.

The two input dialects are intentionally explicit. Visual and LaTeX tabs share the
same TeX source. The Python tab accepts a restricted expression language, not a
Python script. Switching from Python to LaTeX requires entering TeX or loading an
example. Operation **parameters always use Python mathematical notation**, even
when the main expression uses TeX.

## Mathematical coverage

| Area | Included operations |
| --- | --- |
| Algebra | Exact and numerical evaluation, simplify, expand, factor, rational cancellation, common denominators, partial fractions, collect, substitution, equation solution sets, systems, numerical roots, inequalities |
| Calculus | Higher and partial derivatives, indefinite/definite/improper and iterated integrals, one/two-sided limits, Taylor/Fourier series, finite/infinite sums and products, ODEs, supported PDEs, Laplace and Fourier transforms and inverses, gradient, divergence, curl, Laplacian, Hessian, Jacobian, directional derivatives, path/surface integrals, arc length, residues, stationary points, finite differences |
| Linear algebra | Matrices, determinant, inverse, transpose, eigenvalues/eigenvectors, rank, RREF, null space, LU/QR/Cholesky decomposition, vector dot/cross products and norms |
| Discrete maths | Prime factorization, primality, GCD/LCM, modular arithmetic, binomial coefficients, permutations, Diophantine equations |
| Statistics | Exact descriptive statistics, sample/population variance, normal PDF/CDF, binomial PMF/CDF |
| Logic and sets | Boolean simplification, truth tables, set union/intersection/difference, finite sets and intervals |
| Geometry and units | Point distances, circle measurements, triangle measurements, dimension-checked unit conversion |
| Plotting | One to six real functions, local SVG charts, value inspection and resampling on zoom |

**This is broad SymPy coverage, not all of mathematics.** Symbolic algorithms cannot
solve every expression or prove every statement. Unsupported problems produce
explicit errors; uncomputed integrals, transforms, and conditional solution sets
are marked `unevaluated`. There is no fabricated step-by-step proof or derivation.
See [mathematical conventions and limitations](docs/mathematics.md).

## CLI

```bash
# All commands and the full operation catalog
uv run resolvent --help
uv run resolvent operations
uv run resolvent operations integrate
uv run resolvent operations --category 'Linear algebra' --json

# Exact calculus, LaTeX input, and multivariable operations
uv run resolvent calc integrate 'x**2' --param 'bounds=[0,1]'
uv run resolvent calc differentiate '\sin(x)e^{x}' --syntax latex
uv run resolvent calc gradient 'x**2 + y**2' --variables x y
uv run resolvent calc solve_system '[Eq(x+y,5),Eq(x-y,1)]' --variables x y

# Domains, assumptions, matrices, and numerical precision
uv run resolvent calc solve 'x**2=-1' --param domain=complex --format json
uv run resolvent calc simplify 'sqrt(x**2)' --assumptions '{"x":{"positive":true}}'
uv run resolvent calc determinant 'Matrix([[1,2],[3,4]])'
uv run resolvent calc evaluate 'sqrt(2)' --precision 50

# Iterated integral and structured batch requests
uv run resolvent calc integrate 'x*y' --param 'bounds=[["x",0,2],["y",0,3]]'
uv run resolvent batch examples/requests.json
```

Quote expressions so your shell does not interpret `*`, parentheses, or backslashes.
`--format json` prints machine-readable output; `--format latex` prints just the
result's TeX. Repeated `--param key=value` options accept JSON values or mathematical
text. A failed calculation exits with code 2. Batch mode preserves per-item errors
and exits 1 if any item failed. `--timeout` sets a 0.05–300 second wall-clock limit
(default 15 seconds), including worker startup.

## MCP for language models

The MCP server uses the [official Python SDK's FastMCP](https://github.com/modelcontextprotocol/python-sdk)
over stdio. It shares the same parser, limits, schemas, and engine as the UI and CLI.

```bash
uv run resolvent mcp
```

Add this server to an MCP client's configuration, replacing the example absolute
directory with your checkout:

```json
{
  "mcpServers": {
    "resolvent": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/Resolvent", "run", "resolvent", "mcp"]
    }
  }
}
```

Tools:

- `list_operations(category?)`: discover IDs, descriptions, parameter schemas, examples.
- `calculate(request)`: typed input and structured result, including LaTeX and warnings.
- `batch_calculate(requests)`: up to 12 independent requests with per-item errors.

Resources: `resolvent://operations`, `resolvent://syntax`.
Prompt: `solve_carefully(problem)`.

Example tool arguments:

```json
{
  "request": {
    "operation": "integrate",
    "expression": "x**2",
    "syntax": "python",
    "variable": "x",
    "parameters": {"bounds": [0, 1]},
    "precision": 30
  }
}
```

The result contains `result: "1/3"`, `latex: "\\frac{1}{3}"`, `numeric`, `data`,
`status`, `warnings`, and engine elapsed time. Mathematical leaves in `data` are
strings, preserving rational numbers and arbitrary precision. There is no status
logging on protocol stdout.

## Development and verification

```bash
uv sync --extra dev --extra desktop
uv run pytest
uv run ruff check src tests scripts
uv build
```

UI assets are checked in, so users never need a CSS build step. To refresh them:

```bash
uv run python scripts/build_assets.py             # MathLive + standalone Tailwind
uv run python scripts/build_assets.py --css-only  # Keep existing MathLive assets
```

The Python script downloads pinned upstream assets and runs the
[standalone Tailwind CLI](https://tailwindcss.com/docs/installation/tailwind-cli).
It does not use Node.js, npm, a CDN at application runtime, or a development server.
`static/vendor/manifest.json` records bundled MathLive file checksums. The MathLive
license is bundled alongside it; Tailwind's license is in `THIRD_PARTY_NOTICES.md`.

See [architecture](docs/architecture.md), [HTTP API](docs/api.md), and
[mathematical conventions](docs/mathematics.md). The project license is [GPL-3.0](LICENSE).
