"""Discoverable operation metadata, shared with all clients."""

from typing import Any


def param(name, label, default="", kind="expression", help="", choices=None):
    item = {"name": name, "label": label, "default": default, "kind": kind, "help": help}
    if choices:
        item["choices"] = choices
    return item


OPERATIONS: dict[str, dict[str, Any]] = {}


def op(id, label, category, description, expression, parameters=(), defaults=None, variables=None):
    OPERATIONS[id] = {
        "id": id,
        "label": label,
        "category": category,
        "description": description,
        "parameters": list(parameters),
        "example": {
            "operation": id,
            "expression": expression,
            "syntax": "python",
            "variable": "x",
            "variables": variables or [],
            "parameters": defaults or {},
        },
    }


op(
    "evaluate",
    "Evaluate",
    "Algebra",
    "Evaluate a mathematical expression and show a numerical approximation.",
    "sqrt(2) + Rational(1, 3)",
)
op(
    "simplify",
    "Simplify",
    "Algebra",
    "Find a simpler equivalent form using symbolic identities.",
    "sin(x)**2 + cos(x)**2",
)
op("expand", "Expand", "Algebra", "Expand products and powers into a sum of terms.", "(x + 2)**4")
op("factor", "Factor", "Algebra", "Factor a polynomial over the rationals.", "x**4 - 5*x**2 + 4")
op(
    "cancel",
    "Cancel fractions",
    "Algebra",
    "Cancel common polynomial factors in a rational expression.",
    "(x**2 - 1)/(x - 1)",
)
op("together", "Combine fractions", "Algebra", "Combine terms over a common denominator.", "1/x + 1/(x+1)")
op(
    "apart",
    "Partial fractions",
    "Algebra",
    "Decompose a rational function with respect to the variable.",
    "1/(x**2 - 1)",
)
op(
    "collect",
    "Collect terms",
    "Algebra",
    "Group terms by powers of the selected variable.",
    "a*x + b*x + x**2",
)
op(
    "substitute",
    "Substitute",
    "Algebra",
    "Replace symbols simultaneously. Replacements use Python maths syntax.",
    "x**2 + y",
    [param("values", "Replacements", '{"x": "3", "y": "2"}', "json")],
    {"values": {"x": "3", "y": "2"}},
)
domain = param("domain", "Solution domain", "real", "choice", choices=["real", "complex"])
op(
    "solve",
    "Solve equation",
    "Algebra",
    "Find the solution set for one variable, including periodic solutions.",
    "x**2 - 5*x + 6 = 0",
    [domain],
)
op(
    "solve_system",
    "Solve a system",
    "Algebra",
    "Solve a list of equations. The variable list sets the unknowns.",
    "[Eq(x+y, 5), Eq(x-y, 1)]",
    variables=["x", "y"],
)
op(
    "nsolve",
    "Numerical root",
    "Algebra",
    "Find a local numerical root near an initial guess, not every root.",
    "cos(x) - x",
    [param("guess", "Initial guess", "1")],
)
op(
    "inequality",
    "Solve inequality",
    "Algebra",
    "Reduce one inequality, or a list of inequalities, in one variable.",
    "x**2 < 4",
)
op(
    "differentiate",
    "Differentiate",
    "Calculus",
    "Compute an ordinary or partial derivative of any order.",
    "sin(x)*exp(x)",
    [param("order", "Derivative order", 1, "number")],
)
op(
    "integrate",
    "Integrate",
    "Calculus",
    "Compute an antiderivative, definite integral, or iterated integral.",
    "x**2",
    [
        param(
            "bounds",
            "Bounds / iterated limits",
            "",
            "json",
            'Optional: [0, 1] or [["x", 0, 1], ["y", 0, 2]]. Use "oo" for infinity.',
        )
    ],
)
op(
    "limit",
    "Limit",
    "Calculus",
    "Evaluate a limit at a point, including infinity and one-sided limits.",
    "sin(x)/x",
    [
        param("point", "Approach point", "0"),
        param("direction", "Direction", "+-", "choice", choices=["+-", "+", "-"]),
    ],
)
op(
    "series",
    "Taylor series",
    "Calculus",
    "Expand around a point, keeping terms below the requested order.",
    "exp(x)",
    [param("point", "Expansion point", "0"), param("order", "Order", 6, "number")],
)
op(
    "summation",
    "Summation",
    "Calculus",
    "Evaluate a finite or infinite symbolic sum.",
    "1/x**2",
    [param("lower", "Lower bound", "1"), param("upper", "Upper bound", "oo")],
)
op(
    "product",
    "Product",
    "Calculus",
    "Evaluate a finite or infinite symbolic product.",
    "x",
    [param("lower", "Lower bound", "1"), param("upper", "Upper bound", "5")],
)
op(
    "ode",
    "Differential equation",
    "Calculus",
    "Solve an ordinary differential equation in f(x).",
    "Eq(diff(f(x), x), f(x))",
    [param("function", "Unknown function", "f", "text")],
)
op(
    "pde",
    "Partial differential equation",
    "Calculus",
    "Solve PDE classes supported by SymPy, in f(x, y).",
    "Eq(diff(f(x,y), x) + diff(f(x,y), y), 0)",
    [param("function", "Unknown function", "f", "text")],
    variables=["x", "y"],
)
op(
    "laplace",
    "Laplace transform",
    "Calculus",
    "Return a transform plus its convergence plane and conditions.",
    "sin(x)",
    [param("target", "Transform variable", "s", "text")],
)
op(
    "inverse_laplace",
    "Inverse Laplace",
    "Calculus",
    "Recover a function from its Laplace transform.",
    "1/(x**2 + 1)",
    [param("target", "Time variable", "t", "text")],
)
op(
    "fourier",
    "Fourier transform",
    "Calculus",
    "Use the convention exp(-2*pi*I*x*k) for the Fourier transform.",
    "exp(-x**2)",
    [param("target", "Frequency variable", "k", "text")],
)
op(
    "inverse_fourier",
    "Inverse Fourier",
    "Calculus",
    "Use the convention exp(2*pi*I*x*k) for the inverse transform.",
    "exp(-pi*x**2)",
    [param("target", "Output variable", "t", "text")],
)
op(
    "gradient",
    "Gradient",
    "Calculus",
    "Compute the vector of partial derivatives in Cartesian coordinates.",
    "x**2 + y**2 + z**2",
    variables=["x", "y", "z"],
)
op(
    "divergence",
    "Divergence",
    "Calculus",
    "Compute the divergence of a Cartesian vector field.",
    "[x**2, y**2, z**2]",
    variables=["x", "y", "z"],
)
op(
    "curl",
    "Curl",
    "Calculus",
    "Compute the curl of a three-dimensional Cartesian vector field.",
    "[-y, x, 0]",
    variables=["x", "y", "z"],
)
op(
    "hessian",
    "Hessian",
    "Calculus",
    "Compute the matrix of second partial derivatives.",
    "x**3 + x*y + y**2",
    variables=["x", "y"],
)
op(
    "jacobian",
    "Jacobian",
    "Calculus",
    "Compute the derivative matrix of a vector-valued function.",
    "[x*y, sin(x)+y]",
    variables=["x", "y"],
)
op(
    "stationary_points",
    "Stationary points",
    "Calculus",
    "Solve for zero gradient. Check endpoints separately.",
    "x**3 - 3*x",
)
op(
    "finite_difference",
    "Finite difference",
    "Calculus",
    "Approximate a derivative using a symbolic finite-difference stencil.",
    "f(x)",
    [
        param("points", "Stencil points", '["x-1", "x", "x+1"]', "json"),
        param("order", "Derivative order", 1, "number"),
    ],
)
op(
    "laplacian",
    "Laplacian",
    "Calculus",
    "Sum the second partial derivatives in Cartesian coordinates.",
    "x**2+y**2+z**2",
    variables=["x", "y", "z"],
)
op(
    "directional_derivative",
    "Directional derivative",
    "Calculus",
    "Differentiate in a direction; the vector is normalized first.",
    "x**2+y**2",
    [param("direction", "Direction vector", "[1, 1]")],
    variables=["x", "y"],
)
op(
    "arc_length",
    "Arc length",
    "Calculus",
    "Compute the length of a graph y=f(x) between two finite bounds.",
    "x**2",
    [param("lower", "Lower bound", "0"), param("upper", "Upper bound", "1")],
)
op(
    "line_integral",
    "Line integral",
    "Calculus",
    "Integrate a vector field along a parameterized, oriented curve.",
    "[-y, x, 0]",
    [
        param("curve", "Curve components", '["cos(t)", "sin(t)", "0"]', "json"),
        param("parameter", "Curve parameter", "t", "text"),
        param("lower", "Lower bound", "0"),
        param("upper", "Upper bound", "2*pi"),
    ],
    variables=["x", "y", "z"],
)
op(
    "surface_integral",
    "Surface integral",
    "Calculus",
    "Compute oriented flux or a scalar surface integral over a parameterized surface.",
    "[0, 0, 1]",
    [
        param("surface", "Surface components", '["u", "v", "u+v"]', "json"),
        param("bounds", "Parameter bounds", '[["u",0,1],["v",0,1]]', "json"),
        param("mode", "Integral type", "flux", "choice", choices=["flux", "scalar"]),
    ],
    variables=["x", "y", "z"],
)
op(
    "residue",
    "Complex residue",
    "Calculus",
    "Find the residue of a complex function at a point.",
    "1/(x**2+1)",
    [param("point", "Point", "I")],
)
op(
    "fourier_series",
    "Fourier series",
    "Calculus",
    "Return a finite truncation of the Fourier series on an interval.",
    "x**2",
    [
        param("lower", "Lower bound", "-pi"),
        param("upper", "Upper bound", "pi"),
        param("terms", "Nonzero terms", 5, "number"),
    ],
)

matrix = "Matrix([[2, 1], [1, 3]])"
for id, label, description in [
    ("determinant", "Determinant", "Compute the determinant of a square matrix."),
    ("inverse", "Matrix inverse", "Invert a nonsingular square matrix."),
    ("transpose", "Transpose", "Transpose the rows and columns of a matrix."),
    ("eigenvalues", "Eigenvalues", "Return each eigenvalue and its algebraic multiplicity."),
    ("eigenvectors", "Eigenvectors", "Return eigenvalues, multiplicities, and eigenspace bases."),
    ("rank", "Rank", "Compute the rank of a matrix."),
    ("rref", "Row reduction", "Return reduced row echelon form and pivot column indices (zero-based)."),
    ("nullspace", "Null space", "Find a basis for the kernel of a matrix."),
    ("lu", "LU decomposition", "Return L, U, and row permutations."),
    ("qr", "QR decomposition", "Return an orthogonal Q and upper-triangular R."),
    ("cholesky", "Cholesky decomposition", "Factor a Hermitian positive-definite matrix as L*L.H."),
]:
    op(id, label, "Linear algebra", description, matrix)
op(
    "dot",
    "Dot product",
    "Linear algebra",
    "Compute the dot product of two vectors.",
    "[1, 2, 3]",
    [param("other", "Second vector", "[4, 5, 6]")],
)
op(
    "cross",
    "Cross product",
    "Linear algebra",
    "Compute the cross product of two three-dimensional vectors.",
    "[1, 0, 0]",
    [param("other", "Second vector", "[0, 1, 0]")],
)
op("norm", "Vector norm", "Linear algebra", "Compute the Euclidean norm of a vector.", "[3, 4]")
op(
    "factor_integer",
    "Prime factorization",
    "Discrete maths",
    "Factor an integer into primes and multiplicities.",
    "360",
)
op(
    "is_prime",
    "Primality test",
    "Discrete maths",
    "Deterministic below 2**64; a probable-prime test for larger integers.",
    "104729",
)
op(
    "gcd",
    "Greatest common divisor",
    "Discrete maths",
    "Compute the greatest common divisor of two integers or polynomials.",
    "84",
    [param("other", "Second expression", "30")],
)
op(
    "lcm",
    "Least common multiple",
    "Discrete maths",
    "Compute the least common multiple of integers or polynomials.",
    "12",
    [param("other", "Second expression", "18")],
)
op(
    "modulo",
    "Modular arithmetic",
    "Discrete maths",
    "Find the remainder modulo a nonzero number.",
    "2**100",
    [param("modulus", "Modulus", "17")],
)
op(
    "binomial",
    "Combinations",
    "Discrete maths",
    "Compute the binomial coefficient n choose k.",
    "10",
    [param("k", "Choose k", "3")],
)
op(
    "permutations",
    "Permutations",
    "Discrete maths",
    "Count ordered choices of k items from n without replacement.",
    "10",
    [param("k", "Choose k", "3")],
)
op(
    "diophantine",
    "Diophantine equation",
    "Discrete maths",
    "Find integer solutions; tuple entries follow the chosen variable order.",
    "2*x + 3*y - 7",
    variables=["x", "y"],
)
op(
    "statistics",
    "Descriptive statistics",
    "Statistics",
    "Compute count, mean, median, variance, standard deviation, and range.",
    "[2, 4, 4, 4, 5, 5, 7, 9]",
    [param("sample", "Variance convention", "population", "choice", choices=["population", "sample"])],
)
op(
    "normal_distribution",
    "Normal distribution",
    "Statistics",
    "Evaluate the density and cumulative probability at a point.",
    "1.96",
    [param("mean", "Mean", "0"), param("std", "Standard deviation", "1")],
)
op(
    "binomial_distribution",
    "Binomial distribution",
    "Statistics",
    "Evaluate P(X=k), cumulative P(X<=k), mean, and variance.",
    "3",
    [param("n", "Number of trials", "10"), param("p", "Success probability", "1/2")],
)
op(
    "simplify_logic",
    "Simplify logic",
    "Logic & sets",
    "Simplify Boolean logic to conjunctive or disjunctive normal form.",
    "(A & B) | (A & ~B)",
    [param("form", "Normal form", "dnf", "choice", choices=["dnf", "cnf"])],
)
op(
    "truth_table",
    "Truth table",
    "Logic & sets",
    "Enumerate a Boolean expression (up to eight variables).",
    "A & (B | ~C)",
)
for id, label, description in [
    ("set_union", "Set union", "Find elements in either of two sets."),
    ("set_intersection", "Set intersection", "Find elements common to two sets."),
    ("set_difference", "Set difference", "Find elements in the first set but not the second."),
]:
    op(
        id,
        label,
        "Logic & sets",
        description,
        "FiniteSet(1, 2, 3)",
        [param("other", "Second set", "FiniteSet(3, 4, 5)")],
    )
op(
    "distance",
    "Point distance",
    "Geometry",
    "Compute Euclidean distance between points of equal dimension.",
    "[1, 2]",
    [param("other", "Second point", "[4, 6]")],
)
op("circle", "Circle", "Geometry", "Compute area and circumference from a nonnegative radius.", "3")
op(
    "triangle",
    "Triangle",
    "Geometry",
    "Compute perimeter and Heron's area from three valid side lengths.",
    "[3, 4, 5]",
)
op(
    "units",
    "Convert units",
    "Geometry",
    "Convert units such as meter, second, kilogram, joule, and centimeter.",
    "5*meter",
    [param("target", "Target unit", "centimeter", "text")],
)
op(
    "plot",
    "Plot functions",
    "Plotting",
    "Sample real functions in one variable. A list overlays multiple curves.",
    "[sin(x), cos(x)]",
    [
        param("lower", "From", "-2*pi"),
        param("upper", "To", "2*pi"),
        param("samples", "Samples", 501, "number"),
    ],
)


def catalog() -> list[dict[str, Any]]:
    return list(OPERATIONS.values())
