---
name: math
description: Solve math problems, calculations, equations, statistics, algebra, calculus, and numerical operations. Use when the user asks to calculate, compute, solve, evaluate an expression, do math, or asks a numerical question.
metadata: {"clawdbot":{"emoji":"🧮","os":["darwin","linux"]}}
---

# Math

Solve any math problem by writing a Python script, running it, and returning the result. Never attempt to chain multiple tool calls for arithmetic — write one script and execute it once.

## When to use

- User says: "calculate", "compute", "solve", "what is X + Y", "evaluate", "integrate", "derivative", "statistics", "convert", etc.
- Any numerical or symbolic math question.

## How to solve

1. Write a Python script to `workspace/scripts/math_solve.py` with the full logic.
2. Run it with `exec` tool: `python3 workspace/scripts/math_solve.py`
3. Read the output and reply to the user.
4. Delete the script after.

## Script template

```python
#!/usr/bin/env python3
import math
import statistics

# --- solve the problem here ---
result = ...

print(result)
```

## Libraries available (stdlib only, no pip needed)

- `math` — sqrt, log, sin, cos, pi, e, factorial, etc.
- `statistics` — mean, median, stdev, variance
- `decimal` — high-precision arithmetic
- `fractions` — exact rational math
- `cmath` — complex numbers
- `itertools`, `functools` — combinatorics, reduce

## Examples

**Basic arithmetic:**
```python
result = (3**4 + 2**8) / (7 * 11)
print(round(result, 6))
```

**Quadratic formula:**
```python
import math
a, b, c = 2, -5, 3
disc = b**2 - 4*a*c
x1 = (-b + math.sqrt(disc)) / (2*a)
x2 = (-b - math.sqrt(disc)) / (2*a)
print(f"x1 = {x1}, x2 = {x2}")
```

**Statistics:**
```python
import statistics
data = [12, 15, 14, 10, 18, 21, 13]
print(f"Mean: {statistics.mean(data)}")
print(f"Median: {statistics.median(data)}")
print(f"Stdev: {statistics.stdev(data):.4f}")
```

**Combinatorics:**
```python
import math
# Combinations: C(n, k)
n, k = 10, 3
print(math.comb(n, k))
```

**Numerical integration (trapezoidal):**
```python
import math
def f(x):
    return math.sin(x) / x if x != 0 else 1.0

a, b, n = 0.0001, math.pi, 10000
dx = (b - a) / n
total = sum(f(a + i * dx) for i in range(n)) * dx
print(f"Integral ≈ {total:.6f}")
```

## Rules

- **One exec only** — put all steps in one script, never loop across multiple tool calls.
- Always `print()` the result clearly.
- Round floats to a sensible number of decimals (4–6) unless exact.
- If the problem needs `numpy`/`sympy` and they aren't available, use stdlib equivalents (shown above).
- Clean up: delete `workspace/scripts/math_solve.py` after reading the output.
