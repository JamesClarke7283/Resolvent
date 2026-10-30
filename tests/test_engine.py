import pytest
import sympy as sp

from resolvent.catalog import OPERATIONS
from resolvent.engine import compute
from resolvent.models import MathError, MathRequest
from resolvent.parser import MathParser


@pytest.mark.parametrize("operation", list(OPERATIONS))
def test_every_advertised_example_executes(operation):
    result = compute(OPERATIONS[operation]["example"])
    assert result.result
    assert result.latex
    assert result.status in {"ok", "unevaluated"}


def calculate(operation, expression, **kwargs):
    return compute(MathRequest(operation=operation, expression=expression, **kwargs))


def test_python_and_latex_calculus_are_equivalent():
    python = calculate("differentiate", "sin(x)*exp(x)")
    latex = calculate("differentiate", r"\sin(x)e^{x}", syntax="latex")
    p = MathParser()
    assert sp.simplify(p.parse(python.result) - p.parse(latex.result)) == 0


def test_latex_fraction_and_assumptions():
    assert (
        calculate("integrate", r"\frac{x^2}{2}", syntax="latex", parameters={"bounds": [0, 2]}).result
        == "4/3"
    )
    assert calculate("simplify", "sqrt(x**2)", assumptions={"x": {"positive": True}}).result == "x"


def test_exact_decimal_and_python_complex_syntax():
    assert calculate("evaluate", "0.1 + 0.2").result == "3/10"
    assert calculate("evaluate", "(1+2j)*(1-2j)").numeric == "5.000000000000000"


def test_infinite_solution_set_and_domains():
    assert calculate("solve", "x**2 = -1").result == "EmptySet"
    assert calculate("solve", "x**2 = -1", parameters={"domain": "complex"}).result == "{-I, I}"
    result = calculate("solve", "sin(x)=0")
    assert "ImageSet" in result.result


def test_systems_matrices_and_iterated_integrals():
    result = calculate("solve_system", "[Eq(x+y,5),Eq(x-y,1)]", variables=["x", "y"])
    assert result.data == [{"x": "3", "y": "2"}]
    assert calculate("determinant", "Matrix([[1,2],[3,4]])").result == "-2"
    assert calculate("integrate", "x*y", parameters={"bounds": [["x", 0, 2], ["y", 0, 3]]}).result == "9"


def test_limit_series_and_transform():
    assert calculate("limit", "sin(x)/x").result == "1"
    assert "O(x**6)" in calculate("series", "exp(x)").result
    result = calculate("laplace", "1")
    assert result.data["transform"] == "1/s"
    assert result.data["convergence_abscissa"] == "0"


def test_vector_calculus_and_probability():
    assert calculate("curl", "[-y, x, 0]", variables=["x", "y", "z"]).data == [["0"], ["0"], ["2"]]
    result = calculate("statistics", "[1,2,3]", parameters={"sample": "sample"})
    assert result.data["variance"] == "1"
    assert calculate("normal_distribution", "0").data["cdf"] == "1/2"


def test_path_and_surface_integrals():
    assert compute(OPERATIONS["line_integral"]["example"]).result == "2*pi"
    assert compute(OPERATIONS["surface_integral"]["example"]).result == "1"
    assert (
        calculate("surface_integral", "1", variables=["x", "y", "z"], parameters={"mode": "scalar"}).result
        == "sqrt(3)"
    )
    assert calculate("laplacian", "x**2+y**2+z**2", variables=["x", "y", "z"]).result == "6"
    assert calculate("residue", "1/(x**2+1)").result == "-I/2"


def test_unevaluated_result_is_labelled():
    result = calculate("integrate", "f(x)")
    assert result.status == "unevaluated"
    assert any("unevaluated" in warning for warning in result.warnings)
    matrix = calculate("evaluate", "Matrix([[Integral(f(x),x)]])")
    assert matrix.status == "unevaluated"


@pytest.mark.parametrize("text", ["x -", r"\frac{x}{", "x + 1)"])
def test_latex_parser_requires_complete_valid_input(text):
    with pytest.raises(MathError):
        MathParser().parse(text, "latex")


def test_plot_constants_and_discontinuities_are_json_safe():
    result = calculate("plot", "[1,1/x]", parameters={"lower": "-1", "upper": "1", "samples": 101})
    assert result.plot["curves"][0]["y"] == [1.0] * 101
    assert result.plot["curves"][1]["y"][50] is None
    assert "NaN" not in result.model_dump_json()


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os').system('echo pwned')",
        "(1).__class__",
        "[x for x in range(5)]",
        "lambda x: x",
        "open('secrets')",
        "globals()",
        "[1][0]",
        "f(x, **y)",
        "(x := 2)",
        "'abc'",
        "2**10001",
    ],
)
def test_rejects_nonmathematical_python(text):
    with pytest.raises(MathError):
        MathParser().parse(text)


@pytest.mark.parametrize(
    "operation,expression,parameters",
    [
        ("integrate", "x", {"typo": 2}),
        ("differentiate", "x", {"order": -1}),
        ("solve", "x", {"domain": "natural"}),
        ("plot", "x", {"lower": "2", "upper": "1"}),
        ("plot", "x+y", {}),
        ("triangle", "[1,2,9]", {}),
        ("statistics", "[1,x]", {}),
        ("units", "5*meter", {"target": "second"}),
    ],
)
def test_invalid_math_is_reported(operation, expression, parameters):
    with pytest.raises(MathError):
        calculate(operation, expression, parameters=parameters)
