"""Parse mathematical expressions without executing Python source code.

The Python dialect is a deliberately small AST interpreter. SymPy's general
parse_expr/sympify(string) functions evaluate Python, so they are not used here.
"""

import ast
import operator
import re
from typing import Any

import sympy as sp
from sympy.parsing.latex import parse_latex

from resolvent.models import MathError

FUNCTION_NAMES = """
sin cos tan asin acos atan atan2 sinh cosh tanh asinh acosh atanh sec csc cot
exp log sqrt Abs sign floor ceiling Min Max re im conjugate arg factorial
factorial2 binomial gamma loggamma beta erf erfc erfi zeta polylog LambertW
besselj bessely besseli besselk airyai airybi legendre hermite laguerre chebyshevt
Rational Integer Float Eq Ne Lt Le Gt Ge And Or Not Xor Implies Equivalent
Piecewise Matrix ImmutableMatrix diag eye zeros ones det trace transpose
Integral Derivative Sum Product Limit diff integrate simplify expand factor
cancel together apart trigsimp expand_trig powsimp logcombine summation product
gcd lcm isprime nextprime prevprime prime primepi totient divisors factorint
Mod FiniteSet Interval Union Intersection Complement SymmetricDifference
Tuple sin pi
""".split()
FUNCTIONS = {name: getattr(sp, name) for name in FUNCTION_NAMES if callable(getattr(sp, name, None))}
FUNCTIONS.update({"abs": sp.Abs, "ln": sp.log, "N": sp.N})
CONSTANTS = {
    "pi": sp.pi,
    "E": sp.E,
    "e": sp.E,
    "I": sp.I,
    "j": sp.I,
    "oo": sp.oo,
    "inf": sp.oo,
    "Infinity": sp.oo,
    "EulerGamma": sp.EulerGamma,
    "GoldenRatio": sp.GoldenRatio,
    "True": sp.true,
    "False": sp.false,
    "Reals": sp.S.Reals,
    "Complexes": sp.S.Complexes,
    "Integers": sp.S.Integers,
    "Naturals": sp.S.Naturals,
    "EmptySet": sp.S.EmptySet,
    "UniversalSet": sp.S.UniversalSet,
}
RESERVED = set(FUNCTIONS) | set(CONSTANTS)
BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: sp.Mod,
    ast.BitAnd: sp.And,
    ast.BitOr: sp.Or,
}
COMPARISONS = {ast.Eq: sp.Eq, ast.NotEq: sp.Ne, ast.Lt: sp.Lt, ast.LtE: sp.Le, ast.Gt: sp.Gt, ast.GtE: sp.Ge}


class MathParser:
    def __init__(self, assumptions: dict[str, dict[str, bool]] | None = None):
        self.assumptions = assumptions or {}
        self.symbols: dict[str, sp.Symbol] = {}

    def symbol(self, name: str) -> sp.Symbol:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", name) or "__" in name:
            raise MathError(f"Invalid symbol: {name}.")
        if name in RESERVED:
            raise MathError(f"{name} is a reserved mathematical name; choose another variable.")
        if name not in self.symbols:
            self.symbols[name] = sp.Symbol(name, **self.assumptions.get(name, {}))
        return self.symbols[name]

    def parse(self, text: str, syntax: str = "auto") -> Any:
        if not isinstance(text, str) or not text.strip():
            raise MathError("Enter a mathematical expression.")
        if len(text) > 8000:
            raise MathError("Expression is too long (maximum 8,000 characters).")
        text = text.strip()
        if syntax == "auto":
            syntax = "latex" if "\\" in text or "{" in text and "}" in text else "python"
        try:
            if syntax == "latex":
                return self._latex(text)
            text = text.replace("^", "**").replace("−", "-").replace("×", "*").replace("÷", "/")
            # A single top-level '=' is convenient equation notation. Keyword
            # arguments inside function calls are preserved for the AST validator.
            depth = 0
            for i, char in enumerate(text):
                depth += char in "([{"
                depth -= char in ")]}"
                if (
                    char == "="
                    and depth == 0
                    and text[max(0, i - 1) : i] not in "<>=!"
                    and text[i + 1 : i + 2] != "="
                ):
                    left, right = text[:i], text[i + 1 :]
                    return sp.Eq(self.parse(left, "python"), self.parse(right, "python"))
            tree = ast.parse(text, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > 1200:
                raise MathError("Expression is too complex.")
            return self._visit(tree.body)
        except MathError:
            raise
        except Exception as exc:
            raise MathError(f"Could not parse this {syntax} expression: {str(exc)[:240]}") from exc

    def _latex(self, text: str):
        text = re.sub(r"^\$+|\$+$", "", text).strip()
        text = re.sub(r"\\(?:displaystyle|textstyle)\b", "", text)
        text = text.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
        # MathLive exports explicit spacing commands around some constructs.
        text = re.sub(r"\\(?:,|;|!|quad\b|qquad\b)", " ", text)
        if "\\begin" in text or "\\end" in text:
            raise MathError("For matrices use Python input: Matrix([[1, 2], [3, 4]]).")
        result = parse_latex(text, strict=True)
        if not isinstance(result, sp.Basic):
            raise MathError("This LaTeX construct is not supported. Try the Python input tab.")
        replacements = {}
        for symbol in result.free_symbols:
            name = symbol.name.replace("{", "").replace("}", "")
            replacements[symbol] = CONSTANTS[name] if name in CONSTANTS else self.symbol(name)
        return result.xreplace(replacements)

    def _visit(self, node: ast.AST):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return sp.true if node.value else sp.false
            if isinstance(node.value, int):
                if node.value.bit_length() > 4096:
                    raise MathError("Integer literal is too large.")
                return sp.Integer(node.value)
            if isinstance(node.value, float):
                # Decimal literals are exact rationals; N(...) requests an approximation.
                return sp.Rational(str(node.value))
            if isinstance(node.value, complex):
                return sp.Rational(str(node.value.imag)) * sp.I
            raise MathError("Only mathematical numbers are allowed as literals.")
        if isinstance(node, ast.Name):
            return CONSTANTS[node.id] if node.id in CONSTANTS else self.symbol(node.id)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [self._visit(item) for item in node.elts]
            return sp.FiniteSet(*values) if isinstance(node, ast.Set) else values
        if isinstance(node, ast.UnaryOp):
            val = self._visit(node.operand)
            if isinstance(node.op, ast.USub):
                return -val
            if isinstance(node.op, ast.UAdd):
                return val
            if isinstance(node.op, (ast.Not, ast.Invert)):
                return sp.Not(val)
        if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
            left, right = self._visit(node.left), self._visit(node.right)
            if isinstance(node.op, ast.Pow) and right.is_number and sp.Abs(right) > 10000:
                raise MathError("Exponent magnitude is limited to 10,000.")
            return BINOPS[type(node.op)](left, right)
        if isinstance(node, ast.Compare):
            vals = [self._visit(node.left), *(self._visit(x) for x in node.comparators)]
            if any(type(op) not in COMPARISONS for op in node.ops):
                raise MathError("Only mathematical comparisons are supported.")
            return sp.And(*(COMPARISONS[type(op)](a, b) for op, a, b in zip(node.ops, vals, vals[1:])))
        if isinstance(node, ast.BoolOp):
            fn = sp.And if isinstance(node.op, ast.And) else sp.Or
            return fn(*(self._visit(x) for x in node.values))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name.startswith("_") or "__" in name:
                raise MathError("Private names are not supported.")
            if node.keywords:
                raise MathError("Use positional function arguments; set options in operation parameters.")
            args = [self._visit(item) for item in node.args]
            if name in FUNCTIONS:
                return FUNCTIONS[name](*args)
            # Undefined mathematical functions enable differential equations: f(x).
            if not args or name in {
                "eval",
                "exec",
                "compile",
                "getattr",
                "setattr",
                "delattr",
                "globals",
                "locals",
                "vars",
                "open",
                "input",
                "type",
                "dir",
                "help",
            }:
                raise MathError("Only mathematical functions with arguments are supported.")
            self.symbol(name)
            return sp.Function(name)(*args)
        raise MathError("Unsupported Python syntax. Use numbers, symbols, lists, and mathematical functions.")
