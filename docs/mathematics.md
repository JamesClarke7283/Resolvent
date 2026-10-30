# Input, conventions, and limits

## Python mathematical expressions

The parser walks a whitelist of Python AST nodes. It accepts arithmetic, comparisons,
Boolean operators, vectors/lists, and named mathematical functions. It never invokes
Python `eval`, `exec`, or SymPy's string-evaluating `parse_expr`/`sympify` APIs.

- Write `2*x`, not `2x`; `**` is exponentiation. `^` is accepted as a convenience.
- `0.1 + 0.2` is exactly `3/10`. `N(sqrt(2), 30)` explicitly approximates an expression.
- Constants include `pi`, `E`/`e`, `I`/`j`, `oo`/`inf`, `EulerGamma`, and `GoldenRatio`.
- Use `Rational(1,3)` or `1/3` for fractions and `Eq(x**2,4)` or `x**2=4` for equations.
- Systems use `[Eq(x+y,5), Eq(x-y,1)]` and a variable list such as `x, y`.
- Matrices use `Matrix([[1,2],[3,4]])`; a vector can be `[1,2,3]`.
- Sets use `FiniteSet(1,2)`, `{1,2}`, or `Interval(0,1)`. Set operations have explicit operation IDs.
- Undefined mathematical functions such as `f(x)` are supported for ODEs and PDEs.
- `sin`, `cos`, inverse/hyperbolic functions, `log`, `exp`, `sqrt`, `Abs`, factorial,
  gamma/beta, erf, zeta, Bessel functions, selected orthogonal polynomials, and standard
  symbolic calculus constructors are available. See `parser.py` for the exact allowlist.
- Attribute access, arbitrary imports, strings, file access, subscripting, comprehensions,
  lambdas, assignments, and keyword arguments are rejected. This is not a Python REPL.

For the Auto syntax mode, a backslash or braces indicate LaTeX. Explicitly choose
`--syntax python` for brace-style sets to avoid ambiguity.

## LaTeX / MathTeX

Visual input uses MathLive. Server parsing uses SymPy's strict ANTLR LaTeX parser
with the required `antlr4-python3-runtime==4.11.1` dependency.

Supported examples include `\frac{x^2}{2}`, `\sqrt{x}`, `\sin(x)e^x`, integrals,
derivatives, and equations. Display delimiters `$…$`/`$$…$$`, common spacing commands,
and `\dfrac` are normalized. This supports a mathematical subset of TeX, not arbitrary
TeX documents, macros, or every construct the visual editor can display.

Use Python input for matrices, equation lists, piecewise functions, logic, sets,
unit names, and other constructs that cannot be parsed reliably as LaTeX. Matrices
are explicitly rejected in LaTeX with a suggestion for Python syntax. All operation
parameters use Python mathematical notation or JSON regardless of the input tab.

## Conventions

- Symbols have no assumptions unless supplied, e.g. `{"x":{"positive":true}}`.
  Supported assumptions: real, positive, negative, nonnegative, nonzero, integer, finite.
- Single-equation `solve` returns a solution set over the reals by default; `domain=complex`
  changes it. `solve_system` uses SymPy's algebraic solver and can omit special
  parameter branches. Check conditions, excluded denominators, and singular points.
- `nsolve` finds one root near an initial guess, not all roots. No general proof of
  uniqueness is implied. Precision controls numerical output, not an error bound.
- Antiderivatives omit `+C`; add an arbitrary constant when writing a general indefinite
  integral. Iterated integration limits are applied in order from inner to outer.
- Laplace transforms return the convergence abscissa and conditions alongside the
  transform. Fourier uses `exp(-2*pi*I*x*k)`; its inverse uses the positive sign.
- Vector calculus uses Cartesian coordinates. Supply the variables in component order.
- Stationary points are candidates, not classified or globally certified extrema.
- RREF pivot column indices start at zero. Diophantine tuples use the requested variable order.
- Statistics require finite real observations. Select population or sample variance.
- Unit conversion uses full SymPy unit names, e.g. `5*meter` to `centimeter`.
  Symbolic coefficients in unit expressions are not accepted. Temperature offset
  scales such as Celsius are not handled as ordinary multiplicative units.
- The primality test is deterministic below `2**64`; larger values use probable-prime testing.
- Plots are finite samples of real functions, at most six curves and 2,001 samples.
  Nonreal/nonfinite values are gaps. The visible y-range clips extreme values;
  discontinuity detection is heuristic and plots may miss poles or fine features.

## Scope and resource limits

This workbench covers many standard topics; it does not claim complete coverage of
all calculus, geometry, number theory, probability, topology, abstract algebra, or
mathematical research. PDE and ODE support is limited to SymPy's supported classes.
It has no numerical PDE mesh solver, general theorem prover, optimization package,
3-D graphing suite, or step-by-step derivation system.

Symbolic requests run in disposable processes. By default each has 15 seconds wall
time, at most two concurrent workers, and (on Linux) 2 GiB virtual address space plus
a CPU time limit. Input length is limited to 8,000 characters / 1,200 AST nodes;
parameters, integer literals, derivative orders, and output size are bounded too.
These limits protect the local app's responsiveness; OS-level memory/CPU controls
are not applied on non-Linux systems. An adversarial multiuser service would require
additional sandboxing, queueing, authentication, and operational controls.

Unevaluated `Integral`, `Derivative`, `Sum`, `Product`, `Limit`, transform objects,
and `ConditionSet` instances are flagged `status="unevaluated"`. A completed symbolic
expression can still carry explicit conditions or integration constants. Preserve
all warnings when using results in an LLM response.
