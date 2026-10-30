"""Official MCP SDK server. Stdio is reserved exclusively for MCP messages."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from resolvent.catalog import catalog
from resolvent.models import MathError, MathRequest, MathResult
from resolvent.service import MathService


def create_mcp(timeout: float = 15) -> FastMCP:
    server = FastMCP(
        "Resolvent",
        instructions=(
            "A local symbolic mathematics engine. Discover supported operations with "
            "list_operations, then use calculate with a typed request. Python-style "
            "mathematical expressions and LaTeX are accepted; arbitrary Python is not. "
            "Parameters are always Python-style expressions. Preserve domains, assumptions, "
            "warnings, and unevaluated status in your answer. Never claim complete coverage "
            "of mathematics or that a numerical root is exhaustive."
        ),
    )
    service = MathService(timeout)

    @server.tool()
    def list_operations(category: str | None = None) -> list[dict]:
        """List operation IDs, descriptions, parameter schemas, and executable examples."""
        return [
            op for op in catalog() if category is None or op["category"].casefold() == category.casefold()
        ]

    @server.tool()
    async def calculate(request: MathRequest) -> MathResult:
        """Perform exact symbolic mathematics. Results include LaTeX, structured data, and warnings.

        Example: {"operation":"integrate","expression":"x**2","variable":"x",
                  "parameters":{"bounds":[0,1]}}. Syntax may be python, latex, or auto.
        Use list_operations for the full catalog and parameters. No Python code execution.
        """
        try:
            return await service.acalculate(request)
        except MathError as exc:
            raise ToolError(f"{exc.code}: {exc}") from exc

    @server.tool()
    async def batch_calculate(requests: list[MathRequest]) -> list[dict]:
        """Run up to 12 independent calculations sequentially; preserve per-item errors."""
        if not 1 <= len(requests) <= 12:
            raise ToolError("Provide between 1 and 12 requests.")
        results = []
        for request in requests:
            try:
                results.append({"ok": True, "result": (await service.acalculate(request)).model_dump()})
            except MathError as exc:
                results.append({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        return results

    @server.resource("resolvent://operations")
    def operations_resource() -> str:
        """Full operation catalog with examples and parameter definitions."""
        return json.dumps(catalog(), indent=2)

    @server.resource("resolvent://syntax")
    def syntax_resource() -> str:
        return (
            "Use x**2, sin(x), Rational(1,3), Eq(x**2,4), Matrix([[1,2],[3,4]]), "
            "or LaTeX such as \\frac{x^2}{2}. Python input requires explicit multiplication. "
            "Parameters always use Python maths syntax. Assumptions example: "
            '{"x":{"positive":true}}. Unsupported or conditional results are marked unevaluated. '
            "All computations have a wall-clock timeout. Solve works over the reals by default. "
            "Indefinite integrals omit +C. Fourier uses exp(-2*pi*I*x*k)."
        )

    @server.prompt()
    def solve_carefully(problem: str) -> str:
        """Guide a model to use the engine while retaining mathematical qualifications."""
        return (
            f"Solve this mathematics problem using Resolvent: {problem}\n"
            "First identify the variables, domain, and assumptions. Discover the appropriate operation. "
            "Call calculate, check status and warnings, and verify candidate answers by substitution "
            "when possible. Explain any uncomputed or conditional parts without inventing a derivation."
        )

    return server


def run_mcp(timeout: float = 15):
    create_mcp(timeout).run(transport="stdio")
