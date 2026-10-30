"""Symbolic operations. Every public surface calls this single engine."""

import json
import math
import time
import uuid
import warnings
from typing import Any

import numpy as np
import sympy as sp
from sympy.core.relational import Equality
from sympy.logic.boolalg import truth_table
from sympy.physics import units
from sympy.physics.units import convert_to

from resolvent.catalog import OPERATIONS
from resolvent.models import MathError, MathRequest, MathResult
from resolvent.parser import MathParser


def structured(value: Any) -> Any:
    """Lossless mathematical leaves are strings, rather than JSON floats."""
    if isinstance(value, dict):
        return {str(k): structured(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        values = sorted(value, key=str) if isinstance(value, set) else value
        return [structured(v) for v in values]
    if isinstance(value, sp.MatrixBase):
        return [[str(v) for v in row] for row in value.tolist()]
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    return str(value)


def flatten(value):
    if isinstance(value, dict):
        for val in value.values():
            yield from flatten(val)
    elif isinstance(value, (list, tuple, set)):
        for val in value:
            yield from flatten(val)
    else:
        yield value


class Evaluation:
    def __init__(self, request: MathRequest):
        self.req = request
        self.parser = MathParser(request.assumptions)
        self.expr = self.parser.parse(request.expression, request.syntax)
        self.x = self.parser.symbol(request.variable)
        self.variables = [self.parser.symbol(name) for name in request.variables] or [self.x]
        self.notes: list[str] = []
        self.plot = None
        self.spec = OPERATIONS[request.operation]
        self.defaults = {p["name"]: p["default"] for p in self.spec["parameters"]}
        extra = set(request.parameters) - set(self.defaults)
        if extra:
            raise MathError(f"Unknown parameter(s): {', '.join(sorted(extra))}.", "invalid_parameters")
        for field in self.spec["parameters"]:
            if field["kind"] == "choice" and self.arg(field["name"]) not in field["choices"]:
                raise MathError(f"{field['label']}: choose one of {', '.join(field['choices'])}.")

    def arg(self, name):
        value = self.req.parameters.get(name, self.defaults.get(name))
        field = next((field for field in self.spec["parameters"] if field["name"] == name), None)
        if field and field["kind"] == "json" and isinstance(value, str) and value.strip():
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise MathError(f"{field['label']} must be valid JSON.", "invalid_parameters") from exc
        return value

    def parse(self, value):
        if isinstance(value, str):
            return self.parser.parse(value, "python")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return sp.Rational(str(value))
        if isinstance(value, list):
            return [self.parse(v) for v in value]
        raise MathError("A parameter must be a mathematical expression or list.", "invalid_parameters")

    def arg_expr(self, name):
        return self.parse(self.arg(name))

    def integer(self, name, minimum=0, maximum=10000):
        value = self.arg_expr(name)
        if not isinstance(value, sp.Integer) or not minimum <= value <= maximum:
            raise MathError(f"{name} must be an integer from {minimum} to {maximum}.", "invalid_parameters")
        return int(value)

    def scalar(self):
        if not isinstance(self.expr, sp.Basic) or isinstance(self.expr, sp.Set):
            raise MathError("This operation requires a scalar expression.")
        return self.expr

    def matrix(self, value=None):
        value = self.expr if value is None else value
        if isinstance(value, sp.MatrixBase):
            return value
        if isinstance(value, list):
            try:
                return sp.Matrix(value)
            except Exception as exc:
                raise MathError("Use a rectangular matrix or a vector list.") from exc
        raise MathError("Enter a matrix such as Matrix([[1, 2], [3, 4]]) or a vector [1, 2, 3].")

    def residual(self, value=None):
        value = self.expr if value is None else value
        return value.lhs - value.rhs if isinstance(value, Equality) else value

    def run(self):
        operation = self.req.operation
        e, x, vs = self.expr, self.x, self.variables
        unary = {
            "simplify": sp.simplify,
            "expand": sp.expand,
            "factor": sp.factor,
            "cancel": sp.cancel,
            "together": sp.together,
        }
        if operation in unary:
            return unary[operation](e)
        if operation == "evaluate":
            if isinstance(e, list):
                return [v.doit() if hasattr(v, "doit") else v for v in e]
            return e.doit() if hasattr(e, "doit") else e
        if operation == "apart":
            return sp.apart(e, x)
        if operation == "collect":
            return sp.collect(e, x)
        if operation == "substitute":
            values = self.arg("values")
            if not isinstance(values, dict) or len(values) > 24:
                raise MathError("Replacements must be a JSON object of up to 24 symbol/value pairs.")
            result = e.subs(
                {self.parser.symbol(k): self.parse(v) for k, v in values.items()}, simultaneous=True
            )
            return result
        if operation == "solve":
            self.notes.append(
                "Solutions use the selected domain; singularities and branch conditions matter."
            )
            return sp.solveset(e, x, domain=sp.S.Reals if self.arg("domain") == "real" else sp.S.Complexes)
        if operation == "solve_system":
            if not isinstance(e, list):
                raise MathError("Enter a list of equations, for example [Eq(x+y, 5), Eq(x-y, 1)].")
            self.notes.append("System solving may omit parameter-dependent branches; verify special cases.")
            return sp.solve(e, vs, dict=True)
        if operation == "nsolve":
            self.notes.append(
                "A numerical root is local to the initial guess and is not an exhaustive solution set."
            )
            return sp.nsolve(self.residual(), x, self.arg_expr("guess"), prec=self.req.precision)
        if operation == "inequality":
            return sp.reduce_inequalities(e if isinstance(e, list) else [e], x)
        if operation == "differentiate":
            return sp.diff(e, x, self.integer("order", 1, 50))
        if operation == "integrate":
            bounds = self.arg("bounds")
            if bounds is None or bounds == "" or bounds == []:
                self.notes.append("Indefinite integrals omit the arbitrary constant of integration.")
                return sp.integrate(e, x)
            if not isinstance(bounds, list):
                raise MathError("Bounds must be [lower, upper] or a list of [variable, lower, upper] limits.")
            if len(bounds) == 2 and not isinstance(bounds[0], list):
                return sp.integrate(e, (x, self.parse(bounds[0]), self.parse(bounds[1])))
            limits = []
            for bound in bounds:
                if not isinstance(bound, list) or len(bound) != 3:
                    raise MathError("Each iterated limit must be [variable, lower, upper].")
                limits.append((self.parser.symbol(bound[0]), self.parse(bound[1]), self.parse(bound[2])))
            if not 1 <= len(limits) <= 6:
                raise MathError("Use between one and six integration limits.")
            self.notes = []
            return sp.integrate(e, *limits)
        if operation == "limit":
            return sp.limit(e, x, self.arg_expr("point"), dir=self.arg("direction"))
        if operation == "series":
            return sp.series(e, x, self.arg_expr("point"), self.integer("order", 1, 50))
        if operation in {"summation", "product"}:
            func = sp.summation if operation == "summation" else sp.product
            return func(e, (x, self.arg_expr("lower"), self.arg_expr("upper")))
        if operation in {"ode", "pde"}:
            name = self.arg("function")
            self.parser.symbol(name)
            f = sp.Function(name)(x) if operation == "ode" else sp.Function(name)(*vs)
            return sp.dsolve(e, f) if operation == "ode" else sp.pdsolve(e, f)
        if operation in {"laplace", "inverse_laplace", "fourier", "inverse_fourier"}:
            target = self.parser.symbol(self.arg("target"))
            func = {
                "laplace": sp.laplace_transform,
                "inverse_laplace": sp.inverse_laplace_transform,
                "fourier": sp.fourier_transform,
                "inverse_fourier": sp.inverse_fourier_transform,
            }[operation]
            result = func(e, x, target)
            if operation == "laplace" and isinstance(result, tuple):
                return dict(zip(["transform", "convergence_abscissa", "condition"], result))
            return result
        if operation == "gradient":
            return sp.Matrix([sp.diff(e, v) for v in vs])
        if operation == "hessian":
            return sp.hessian(e, vs)
        if operation == "jacobian":
            return self.matrix().jacobian(vs)
        if operation in {"divergence", "curl"}:
            vec = self.matrix()
            if vec.cols != 1 or len(vec) != len(vs):
                raise MathError("Provide a vector and one variable for each component.")
            if operation == "divergence":
                return sum(sp.diff(component, v) for component, v in zip(vec, vs))
            if len(vs) != 3:
                raise MathError("Curl requires three components and three variables, usually x, y, z.")
            return sp.Matrix(
                [
                    sp.diff(vec[2], vs[1]) - sp.diff(vec[1], vs[2]),
                    sp.diff(vec[0], vs[2]) - sp.diff(vec[2], vs[0]),
                    sp.diff(vec[1], vs[0]) - sp.diff(vec[0], vs[1]),
                ]
            )
        if operation == "stationary_points":
            self.notes.append(
                "These are stationary-point candidates, not classified extrema or boundary optima."
            )
            return sp.solve([sp.diff(e, v) for v in vs], vs, dict=True)
        if operation == "finite_difference":
            points = self.arg_expr("points")
            if not isinstance(points, list) or not 2 <= len(points) <= 20:
                raise MathError("Provide a list of 2–20 stencil points.")
            return sp.Derivative(e, x, self.integer("order", 1, len(points) - 1)).as_finite_difference(points)
        if operation == "laplacian":
            return sum(sp.diff(e, v, 2) for v in vs)
        if operation == "directional_derivative":
            direction = self.matrix(self.arg_expr("direction"))
            if direction.shape != (len(vs), 1):
                raise MathError("The direction vector must have one component per variable.")
            norm = direction.norm()
            if norm == 0:
                raise MathError("A direction vector cannot be zero.")
            return sp.simplify(sp.Matrix([sp.diff(e, v) for v in vs]).dot(direction) / norm)
        if operation == "arc_length":
            lower, upper = self.arg_expr("lower"), self.arg_expr("upper")
            if (
                lower.is_real is not True
                or upper.is_real is not True
                or lower.is_finite is not True
                or upper.is_finite is not True
                or (upper - lower).is_nonnegative is not True
            ):
                raise MathError("Arc length requires finite real bounds with lower <= upper.")
            return sp.integrate(sp.sqrt(1 + sp.diff(e, x) ** 2), (x, lower, upper))
        if operation == "line_integral":
            curve = self.arg_expr("curve")
            if not isinstance(curve, list) or len(curve) != len(vs):
                raise MathError("Give one curve component for each coordinate variable.")
            parameter = self.parser.symbol(self.arg("parameter"))
            if parameter in vs:
                raise MathError("The curve parameter must differ from the coordinate variables.")
            field = self.matrix()
            if field.shape != (len(vs), 1):
                raise MathError("The vector field must have one component per coordinate variable.")
            replacement = dict(zip(vs, curve))
            integrand = field.subs(replacement, simultaneous=True).dot(sp.Matrix(curve).diff(parameter))
            return sp.integrate(integrand, (parameter, self.arg_expr("lower"), self.arg_expr("upper")))
        if operation == "surface_integral":
            surface, bounds = self.arg_expr("surface"), self.arg("bounds")
            if len(vs) != 3 or not isinstance(surface, list) or len(surface) != 3:
                raise MathError("A surface needs three components and three coordinate variables.")
            if (
                not isinstance(bounds, list)
                or len(bounds) != 2
                or any(not isinstance(bound, list) or len(bound) != 3 for bound in bounds)
            ):
                raise MathError('Use two parameter bounds, e.g. [["u",0,1],["v",0,1]].')
            u, v = [self.parser.symbol(bound[0]) for bound in bounds]
            if u == v or u in vs or v in vs:
                raise MathError("Surface parameters must be distinct from each other and the coordinates.")
            position = sp.Matrix(surface)
            normal = position.diff(u).cross(position.diff(v))
            replacements = dict(zip(vs, surface))
            if self.arg("mode") == "flux":
                field = self.matrix()
                if field.shape != (3, 1):
                    raise MathError("Flux requires a three-component vector field.")
                integrand = field.subs(replacements, simultaneous=True).dot(normal)
                self.notes.append(
                    "Orientation follows the first parameter derivative crossed with the second."
                )
            else:
                integrand = self.scalar().subs(replacements, simultaneous=True) * normal.norm()
            limits = [
                (symbol, self.parse(bound[1]), self.parse(bound[2])) for symbol, bound in zip([u, v], bounds)
            ]
            return sp.integrate(integrand, *limits)
        if operation == "residue":
            return sp.residue(e, x, self.arg_expr("point"))
        if operation == "fourier_series":
            return sp.fourier_series(e, (x, self.arg_expr("lower"), self.arg_expr("upper"))).truncate(
                self.integer("terms", 1, 30)
            )
        matrix_ops = {
            "determinant": "det",
            "inverse": "inv",
            "transpose": "transpose",
            "eigenvalues": "eigenvals",
            "eigenvectors": "eigenvects",
            "rank": "rank",
            "rref": "rref",
            "nullspace": "nullspace",
            "lu": "LUdecomposition",
            "qr": "QRdecomposition",
            "cholesky": "cholesky",
        }
        if operation in matrix_ops:
            result = getattr(self.matrix(), matrix_ops[operation])()
            if operation == "rref":
                return {"matrix": result[0], "pivot_columns": result[1]}
            if operation == "lu":
                return dict(zip(["L", "U", "row_swaps"], result))
            if operation == "qr":
                return dict(zip(["Q", "R"], result))
            return result
        if operation in {"dot", "cross"}:
            return getattr(self.matrix(), operation)(self.matrix(self.arg_expr("other")))
        if operation == "norm":
            return self.matrix().norm()
        if operation in {"factor_integer", "is_prime"}:
            if not isinstance(e, sp.Integer):
                raise MathError("Enter an integer.")
            return sp.factorint(e) if operation == "factor_integer" else bool(sp.isprime(e))
        if operation in {"gcd", "lcm"}:
            return getattr(sp, operation)(e, self.arg_expr("other"))
        if operation == "modulo":
            if self.arg_expr("modulus") == 0:
                raise MathError("Modulus cannot be zero.")
            return sp.Mod(e, self.arg_expr("modulus"))
        if operation in {"binomial", "permutations"}:
            k = self.arg_expr("k")
            if not isinstance(e, sp.Integer) or not isinstance(k, sp.Integer) or not 0 <= k <= e <= 10000:
                raise MathError("Use integers 0 <= k <= n <= 10000.")
            return sp.binomial(e, k) if operation == "binomial" else sp.factorial(e) / sp.factorial(e - k)
        if operation == "diophantine":
            return sp.diophantine(self.residual(), syms=vs)
        if operation == "statistics":
            if not isinstance(e, list) or not 1 <= len(e) <= 10000:
                raise MathError("Enter a nonempty list of real numbers.")
            if any(v.is_real is not True or v.is_finite is not True or v.free_symbols for v in e):
                raise MathError("Descriptive statistics require finite real numbers.")
            n = len(e)
            sample = self.arg("sample") == "sample"
            if sample and n < 2:
                raise MathError("Sample variance needs at least two observations.")
            ordered = sorted(e, key=lambda v: float(v))
            mean = sum(e) / n
            variance = sum((v - mean) ** 2 for v in e) / (n - 1 if sample else n)
            return {
                "count": n,
                "mean": mean,
                "median": (ordered[(n - 1) // 2] + ordered[n // 2]) / 2,
                "variance": variance,
                "standard_deviation": sp.sqrt(variance),
                "minimum": ordered[0],
                "maximum": ordered[-1],
            }
        if operation == "normal_distribution":
            mu, sigma = self.arg_expr("mean"), self.arg_expr("std")
            if sigma.is_positive is not True:
                raise MathError("Standard deviation must be positive; provide an assumption for a symbol.")
            z = (e - mu) / sigma
            return {
                "pdf": sp.exp(-z * z / 2) / (sigma * sp.sqrt(2 * sp.pi)),
                "cdf": (1 + sp.erf(z / sp.sqrt(2))) / 2,
                "mean": mu,
                "variance": sigma * sigma,
            }
        if operation == "binomial_distribution":
            n, p = self.integer("n", 0, 10000), self.arg_expr("p")
            if p.is_number is not True or p.is_real is not True or not 0 <= p <= 1:
                raise MathError("Success probability must be a real number between 0 and 1.")
            if not isinstance(e, sp.Integer) or not 0 <= e <= n:
                raise MathError("k must be an integer between 0 and n.")
            return {
                "pmf": sp.binomial(n, e) * p**e * (1 - p) ** (n - e),
                "cdf": sum(sp.binomial(n, k) * p**k * (1 - p) ** (n - k) for k in range(int(e) + 1)),
                "mean": n * p,
                "variance": n * p * (1 - p),
            }
        if operation == "simplify_logic":
            return sp.simplify_logic(e, form=self.arg("form"))
        if operation == "truth_table":
            symbols = sorted(e.free_symbols, key=str)
            if len(symbols) > 8:
                raise MathError("Truth tables support at most eight variables.")
            return {
                "variables": [str(s) for s in symbols],
                "rows": [{"inputs": row, "output": bool(val)} for row, val in truth_table(e, symbols)],
            }
        if operation in {"set_union", "set_intersection", "set_difference"}:
            other = self.arg_expr("other")
            if not isinstance(e, sp.Set) or not isinstance(other, sp.Set):
                raise MathError("Both inputs must be sets, such as FiniteSet(1, 2) or Interval(0, 1).")
            return {
                "set_union": sp.Union,
                "set_intersection": sp.Intersection,
                "set_difference": sp.Complement,
            }[operation](e, other)
        if operation == "distance":
            a, b = self.matrix(), self.matrix(self.arg_expr("other"))
            if a.shape != b.shape or a.cols != 1:
                raise MathError("Points must be vectors with the same dimension.")
            return (a - b).norm()
        if operation == "circle":
            if e.is_nonnegative is not True:
                raise MathError("Radius must be nonnegative; set an assumption for symbolic radii.")
            return {"area": sp.pi * e**2, "circumference": 2 * sp.pi * e}
        if operation == "triangle":
            if not isinstance(e, list) or len(e) != 3 or any(v.is_positive is not True for v in e):
                raise MathError("Enter three positive side lengths.")
            a, b, c = e
            if any(test is not sp.true for test in [a + b > c, b + c > a, c + a > b]):
                raise MathError("Side lengths must satisfy the strict triangle inequality.")
            s = sum(e) / 2
            return {"perimeter": 2 * s, "area": sp.sqrt(s * (s - a) * (s - b) * (s - c))}
        if operation == "units":
            return self.convert_units()
        if operation == "plot":
            return self.plot_functions()
        raise MathError(f"Operation {operation!r} is not implemented.", "unknown_operation")

    def convert_units(self):
        from sympy.physics.units import Quantity

        def replace_units(expr):
            replacements = {}
            for symbol in expr.free_symbols:
                unit = getattr(units, str(symbol), None)
                if not isinstance(unit, Quantity):
                    raise MathError(f"Unknown unit: {symbol}. Use full names such as meter or kilogram.")
                replacements[symbol] = unit
            return expr.xreplace(replacements)

        source = replace_units(self.expr)
        target = replace_units(self.arg_expr("target"))
        result = convert_to(source, target)
        # Incompatible units are left unchanged by SymPy; never claim success.
        quotient = sp.simplify(result / target)
        if quotient.has(Quantity):
            raise MathError("The source and target units have incompatible dimensions.")
        return result

    def plot_functions(self):
        exprs = self.expr if isinstance(self.expr, list) else [self.expr]
        if not 1 <= len(exprs) <= 6:
            raise MathError("Plot one to six functions at a time.")
        lo, hi = float(self.arg_expr("lower")), float(self.arg_expr("upper"))
        if not math.isfinite(lo) or not math.isfinite(hi) or not lo < hi:
            raise MathError("Plot bounds must be finite real numbers with lower < upper.")
        count = self.integer("samples", 32, 2001)
        xs = np.linspace(lo, hi, count)
        curves = []
        for expr in exprs:
            if not isinstance(expr, sp.Expr) or expr.free_symbols - {self.x}:
                raise MathError("Each plotted function may only contain the selected variable.")
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore")
                fn = sp.lambdify(self.x, expr, modules="numpy", dummify=True, cse=True)
                values = np.asarray(fn(xs), dtype=complex)
                values = np.broadcast_to(values, xs.shape)
            ys = [
                float(v.real) if np.isfinite(v) and abs(v.imag) < 1e-10 and abs(v.real) < 1e100 else None
                for v in values
            ]
            if not any(v is not None for v in ys):
                raise MathError(f"{expr} has no finite real values in this interval.")
            curves.append({"label": str(expr), "latex": sp.latex(expr), "y": ys})
        self.plot = {"x": xs.tolist(), "curves": curves, "variable": str(self.x), "lower": lo, "upper": hi}
        self.notes.append("Plots use finite samples; poles and fine features can be missed. Zoom to inspect.")
        return self.expr


def compute(request: MathRequest | dict) -> MathResult:
    """Run in the isolated service worker when handling untrusted requests."""
    start = time.perf_counter()
    request = request if isinstance(request, MathRequest) else MathRequest.model_validate(request)
    if request.operation not in OPERATIONS:
        raise MathError(f"Unknown operation: {request.operation}.", "unknown_operation")
    try:
        evaluation = Evaluation(request)
        result = evaluation.run()
        text = str(result)
        if len(text) > 60000:
            raise MathError(
                "The result is too large to display. Reduce the expression or requested order.",
                "result_limit",
            )
        result_latex = sp.latex(result)
        numeric = None
        if isinstance(result, (sp.Expr, sp.MatrixBase)) and not result.free_symbols:
            numeric = str(result.evalf(request.precision))
        unfinished = (
            sp.Integral,
            sp.Derivative,
            sp.Sum,
            sp.Product,
            sp.Limit,
            sp.ConditionSet,
            sp.LaplaceTransform,
            sp.InverseLaplaceTransform,
            sp.FourierTransform,
            sp.InverseFourierTransform,
        )
        pending = any(
            isinstance(v, (sp.Basic, sp.MatrixBase)) and v.has(*unfinished) for v in flatten(result)
        )
        if pending:
            evaluation.notes.append("The engine left part of the result unevaluated or conditional.")
        return MathResult(
            id=uuid.uuid4().hex,
            operation=request.operation,
            input=str(evaluation.expr),
            input_latex=sp.latex(evaluation.expr),
            result=text,
            latex=result_latex,
            numeric=numeric,
            data=structured(result),
            status="unevaluated" if pending else "ok",
            warnings=evaluation.notes,
            elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
            plot=evaluation.plot,
        )
    except MathError:
        raise
    except NotImplementedError as exc:
        raise MathError(
            f"The symbolic engine cannot currently solve this case: {str(exc)[:250]}", "not_implemented"
        ) from exc
    except Exception as exc:
        raise MathError(
            f"Unable to complete {request.operation}: {str(exc)[:300]}", "calculation_error"
        ) from exc
