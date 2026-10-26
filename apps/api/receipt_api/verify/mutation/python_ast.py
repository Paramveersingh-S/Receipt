import ast
import copy
import difflib
import re
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import structlog
from pydantic import BaseModel

from receipt_api.schemas import MutantSurvivor, MutationResults
from receipt_api.verify.sandbox import SandboxConfig, run_in_sandbox
from receipt_api.verify.stacks.base import StackAdapter, TestStatus

logger = structlog.get_logger(__name__)


class Mutant(BaseModel):
    id: str
    file: str
    line: int
    op: str
    original_snippet: str
    mutated_snippet: str
    diff: str
    full_mutated_code: str


COMPARE_OPS = {
    ast.Gt: (ast.GtE, "> to >="),
    ast.GtE: (ast.Gt, ">= to >"),
    ast.Lt: (ast.LtE, "< to <="),
    ast.LtE: (ast.Lt, "<= to <"),
    ast.Eq: (ast.NotEq, "== to !="),
    ast.NotEq: (ast.Eq, "!= to =="),
}

BIN_OPS = {
    ast.Add: (ast.Sub, "+ to -"),
    ast.Sub: (ast.Add, "- to +"),
    ast.Mult: (ast.FloorDiv, "* to //"),
    ast.Div: (ast.Mult, "/ to *"),
    ast.FloorDiv: (ast.Div, "// to /"),
}

BOOL_OPS = {
    ast.And: (ast.Or, "and to or"),
    ast.Or: (ast.And, "or to and"),
}


def parse_diff_changed_lines(diff_text: str) -> Dict[str, Set[int]]:
    """Extract line numbers of added or modified lines per file from unified diff."""
    changed: Dict[str, Set[int]] = {}
    current_file = ""
    current_line = 0

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            changed.setdefault(current_file, set())
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                current_line = int(m.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file:
                changed[current_file].add(current_line)
            current_line += 1
        elif not line.startswith("-"):
            current_line += 1

    return changed


class MutationASTTransformer(ast.NodeTransformer):
    """Generates a single mutation at a designated target node line and index."""

    def __init__(self, target_line: int, target_idx: int):
        self.target_line = target_line
        self.target_idx = target_idx
        self.current_idx = 0
        self.mutation_applied: Optional[str] = None

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if node.lineno == self.target_line:
            for idx, op in enumerate(node.ops):
                op_type = type(op)
                if op_type in COMPARE_OPS:
                    if self.current_idx == self.target_idx:
                        new_op_cls, desc = COMPARE_OPS[op_type]
                        node.ops[idx] = new_op_cls()
                        self.mutation_applied = f"COMPARE_{desc}"
                        self.current_idx += 1
                        return node
                    self.current_idx += 1
        return self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        if node.lineno == self.target_line:
            op_type = type(node.op)
            if op_type in BIN_OPS:
                if self.current_idx == self.target_idx:
                    new_op_cls, desc = BIN_OPS[op_type]
                    node.op = new_op_cls()
                    self.mutation_applied = f"ARITH_{desc}"
                    self.current_idx += 1
                    return node
                self.current_idx += 1
        return self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        if node.lineno == self.target_line:
            op_type = type(node.op)
            if op_type in BOOL_OPS:
                if self.current_idx == self.target_idx:
                    new_op_cls, desc = BOOL_OPS[op_type]
                    node.op = new_op_cls()
                    self.mutation_applied = f"BOOL_{desc}"
                    self.current_idx += 1
                    return node
                self.current_idx += 1
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if node.lineno == self.target_line:
            # Round to Int or Int to Round
            if isinstance(node.func, ast.Name):
                if node.func.id == "round":
                    if self.current_idx == self.target_idx:
                        node.func.id = "int"
                        self.mutation_applied = "ROUND_TO_INT"
                        self.current_idx += 1
                        return node
                    self.current_idx += 1
                elif node.func.id == "int":
                    if self.current_idx == self.target_idx:
                        node.func.id = "round"
                        self.mutation_applied = "INT_TO_ROUND"
                        self.current_idx += 1
                        return node
                    self.current_idx += 1
        return self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if node.lineno == self.target_line:
            if isinstance(node.value, bool):
                if self.current_idx == self.target_idx:
                    node.value = not node.value
                    self.mutation_applied = f"BOOL_CONST_INVERT_{node.value}"
                    self.current_idx += 1
                    return node
                self.current_idx += 1
            elif isinstance(node.value, int) and 0 <= node.value <= 1000:
                if self.current_idx == self.target_idx:
                    node.value = node.value + 1
                    self.mutation_applied = f"INT_OFF_BY_ONE_{node.value}"
                    self.current_idx += 1
                    return node
                self.current_idx += 1
        return self.generic_visit(node)


def generate_mutants_for_file(
    file_path: Path,
    relative_path: str,
    changed_lines: Optional[Set[int]] = None,
    max_per_file: int = 15,
) -> List[Mutant]:
    """Generate viable AST mutants for specified lines in a Python file."""
    if not file_path.exists():
        return []

    try:
        source_code = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code, filename=str(file_path))
    except Exception:
        return []

    mutants: List[Mutant] = []
    lines = source_code.splitlines()

    # Determine lines to mutate
    lines_to_target = changed_lines if changed_lines else set(range(1, len(lines) + 1))

    # Priority lines: money, pricing, calculations first
    sorted_lines = sorted(
        list(lines_to_target),
        key=lambda ln: 0 if 1 <= ln <= len(lines) and any(w in lines[ln - 1].lower() for w in ["price", "cents", "total", "discount", "tax"]) else 1,
    )

    for line_num in sorted_lines:
        if line_num < 1 or line_num > len(lines):
            continue
        original_line = lines[line_num - 1]
        if original_line.strip().startswith("#") or not original_line.strip():
            continue

        # Try up to 4 mutation sites per line
        for site_idx in range(4):
            tree_copy = copy.deepcopy(tree)
            transformer = MutationASTTransformer(target_line=line_num, target_idx=site_idx)
            mutated_tree = transformer.visit(tree_copy)

            if transformer.mutation_applied:
                try:
                    mutated_code = ast.unparse(mutated_tree)
                    # Verify syntax
                    ast.parse(mutated_code)
                except Exception:
                    continue

                mutated_lines = mutated_code.splitlines()
                mutated_snippet = mutated_lines[line_num - 1] if line_num - 1 < len(mutated_lines) else ""

                diff = "".join(
                    difflib.unified_diff(
                        [original_line + "\n"],
                        [mutated_snippet + "\n"],
                        fromfile=f"a/{relative_path}",
                        tofile=f"b/{relative_path}",
                        lineterm="",
                    )
                )

                mutant_id = f"mut_{relative_path.replace('/', '_').replace('.', '_')}_{line_num}_{site_idx}"
                mutants.append(
                    Mutant(
                        id=mutant_id,
                        file=relative_path,
                        line=line_num,
                        op=transformer.mutation_applied,
                        original_snippet=original_line.strip(),
                        mutated_snippet=mutated_snippet.strip(),
                        diff=diff,
                        full_mutated_code=mutated_code,
                    )
                )

                if len(mutants) >= max_per_file:
                    return mutants

    return mutants


def generate_mutants_for_diff(
    repo_path: Path,
    diff_text: str,
    cap: int = 40,
) -> List[Mutant]:
    """Generate mutants strictly located within modified line ranges of a PR diff."""
    changed_map = parse_diff_changed_lines(diff_text)
    mutants: List[Mutant] = []

    for rel_path, lines in changed_map.items():
        if not rel_path.endswith(".py"):
            continue
        full_path = repo_path / rel_path
        file_mutants = generate_mutants_for_file(full_path, rel_path, changed_lines=lines, max_per_file=cap)
        mutants.extend(file_mutants)
        if len(mutants) >= cap:
            break

    # If diff was empty (e.g. testing local branch), scan python files directly
    if not mutants:
        for py_file in repo_path.glob("**/*.py"):
            if "test" in py_file.name or ".venv" in str(py_file):
                continue
            rel_p = str(py_file.relative_to(repo_path)).replace("\\", "/")
            file_mutants = generate_mutants_for_file(py_file, rel_p, max_per_file=10)
            mutants.extend(file_mutants)
            if len(mutants) >= cap:
                break

    return mutants[:cap]


def execute_mutation_analysis(
    repo_path: Path,
    mutants: List[Mutant],
    stack: StackAdapter,
    config: SandboxConfig,
    timeout_per_mutant: int = 15,
    on_tick_cb: Optional[Callable[[int, int, int], None]] = None,
) -> MutationResults:
    """Execute test suite against each mutant in the sandbox; measure killed vs survived."""
    if not mutants:
        return MutationResults(
            mutants=0,
            killed=0,
            survived=0,
            timeout=0,
            score=1.0,
            survivors=[],
        )

    killed = 0
    survived = 0
    timed_out = 0
    survivors: List[MutantSurvivor] = []

    for idx, mutant in enumerate(mutants, start=1):
        target_file = repo_path / mutant.file
        if not target_file.exists():
            continue

        original_content = target_file.read_text(encoding="utf-8")
        try:
            # 1. Apply mutation in place
            target_file.write_text(mutant.full_mutated_code, encoding="utf-8")

            # 2. Run tests in sandbox
            mutant_config = SandboxConfig(
                timeout_seconds=timeout_per_mutant,
                network_enabled=False,
            )
            run_res = run_in_sandbox(repo_path=repo_path, stack=stack, config=mutant_config)

            # 3. Check if killed (any test failed) or survived (all tests passed)
            any_failure = any(t.status != TestStatus.PASS for t in run_res.test_results)
            if run_res.exit_code != 0 or any_failure:
                killed += 1
            else:
                survived += 1
                survivors.append(
                    MutantSurvivor(
                        file=mutant.file,
                        line=mutant.line,
                        op=mutant.op,
                        diff=mutant.diff,
                    )
                )
        except Exception as e:
            logger.warning("mutant_execution_error", mutant_id=mutant.id, error=str(e))
            killed += 1  # Unhandled exception/crash is treated as killed
        finally:
            # 4. Strictly restore original content
            target_file.write_text(original_content, encoding="utf-8")

        # Emit mutation tick
        if on_tick_cb:
            on_tick_cb(killed, survived, len(mutants))

    total = killed + survived + timed_out
    score = round(killed / total, 2) if total > 0 else 1.0

    return MutationResults(
        mutants=total,
        killed=killed,
        survived=survived,
        timeout=timed_out,
        score=score,
        survivors=survivors,
    )
