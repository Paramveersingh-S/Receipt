import pytest
from pathlib import Path

from receipt_api.verify.mutation.python_ast import (
    generate_mutants_for_file,
    generate_mutants_for_diff,
    execute_mutation_analysis,
    parse_diff_changed_lines,
)
from receipt_api.verify.sandbox import SandboxConfig
from receipt_api.verify.stacks.python import PythonStackAdapter


def test_parse_diff_changed_lines():
    diff_text = """--- a/shop/pricing.py
+++ b/shop/pricing.py
@@ -10,4 +10,5 @@
 def calculate_total():
+    x = 1
+    y = 2
     return x + y
"""
    changed = parse_diff_changed_lines(diff_text)
    assert "shop/pricing.py" in changed
    assert 10 in changed["shop/pricing.py"] or 11 in changed["shop/pricing.py"]


def test_generate_mutants_for_file(tmp_path):
    py_file = tmp_path / "calc.py"
    py_file.write_text(
        "def compute(a, b):\n"
        "    if a > 10:\n"
        "        return round(a + b)\n"
        "    return a - b\n",
        encoding="utf-8",
    )

    mutants = generate_mutants_for_file(py_file, "calc.py")
    assert len(mutants) > 0

    ops = [m.op for m in mutants]
    # Check that comparison or arithmetic or round mutants were generated
    assert any("COMPARE" in op or "ARITH" in op or "ROUND" in op for op in ops)


def test_execute_mutation_analysis(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"\n', encoding="utf-8")

    calc_file = repo_dir / "calc.py"
    calc_file.write_text(
        "def add(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    test_file = repo_dir / "test_calc.py"
    test_file.write_text(
        "from calc import add\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    mutants = generate_mutants_for_file(calc_file, "calc.py")
    assert len(mutants) > 0

    stack = PythonStackAdapter()
    config = SandboxConfig(timeout_seconds=10)

    ticks = []
    def on_tick(k, s, tot):
        ticks.append((k, s, tot))

    results = execute_mutation_analysis(
        repo_path=repo_dir,
        mutants=mutants,
        stack=stack,
        config=config,
        on_tick_cb=on_tick,
    )

    assert results.mutants > 0
    # Mutation replacing + with - must be killed by assert add(2, 3) == 5!
    assert results.killed > 0
    assert results.score > 0.0
    assert len(ticks) > 0
