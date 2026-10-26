import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel


class Violation(BaseModel):
    check_id: str
    file: str
    line: int
    message: str
    hunk: Optional[str] = None
    severity: str = "block"


MONEY_TERMS = {
    "price", "cents", "amount", "discount", "total", "subtotal", "cost",
    "fee", "balance", "charge", "refund", "tip", "rate", "tax"
}

PII_TERMS = {
    "card_number", "card_num", "cvv", "cvc", "credit_card", "card_cvv",
    "password", "ssn", "secret_key"
}


def _is_money_name(name: str) -> bool:
    name_lower = name.lower()
    return any(term in name_lower for term in MONEY_TERMS)


class ScarASTVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, lines: List[str]):
        self.filename = filename
        self.lines = lines
        self.violations: List[Violation] = []
        self.in_loop = False
        self.current_func: Optional[str] = None

    def _get_line_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        prev_func = self.current_func
        self.current_func = node.name

        # Check 5: missing-auth-dependency on FastAPI route handlers
        is_route = False
        for dec in node.decorator_list:
            dec_src = ast.unparse(dec) if hasattr(ast, "unparse") else ""
            if any(method in dec_src for method in [".get(", ".post(", ".put(", ".delete(", ".patch("]):
                # Exclude explicitly public routes
                if not any(pub in dec_src.lower() for pub in ["health", "docs", "openapi", "public", "webhook"]):
                    is_route = True

        if is_route and not node.name.startswith("public_"):
            has_auth = False
            for arg in node.args.args + node.args.kwonlyargs:
                # check type annotation or default Depends
                pass
            # Check defaults
            for default in node.args.defaults + [d for d in node.args.kw_defaults if d]:
                default_src = ast.unparse(default) if hasattr(ast, "unparse") else ""
                if "depends" in default_src.lower() and any(a in default_src.lower() for a in ["auth", "user", "token"]):
                    has_auth = True
                    break

            if not has_auth:
                self.violations.append(
                    Violation(
                        check_id="missing-auth-dependency",
                        file=self.filename,
                        line=node.lineno,
                        message=f"API route handler '{node.name}' is missing authentication dependency (e.g. Depends(require_auth)).",
                        hunk=self._get_line_snippet(node.lineno),
                        severity="block",
                    )
                )

        # Check 7: non-reversible-migration
        if node.name == "downgrade":
            # Check if empty or only pass
            is_empty = False
            if len(node.body) == 1:
                stmt = node.body[0]
                if isinstance(stmt, ast.Pass):
                    is_empty = True
                elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, (ast.Constant, ast.Ellipsis)):
                    is_empty = True
                elif isinstance(stmt, ast.Return) and stmt.value is None:
                    is_empty = True

            if is_empty:
                self.violations.append(
                    Violation(
                        check_id="non-reversible-migration",
                        file=self.filename,
                        line=node.lineno,
                        message="Migration downgrade() function is empty or contains only 'pass'; migrations must be reversible.",
                        hunk=self._get_line_snippet(node.lineno),
                        severity="block",
                    )
                )

        self.generic_visit(node)
        self.current_func = prev_func

    def visit_For(self, node: ast.For) -> Any:
        prev = self.in_loop
        self.in_loop = True
        self.generic_visit(node)
        self.in_loop = prev

    def visit_While(self, node: ast.While) -> Any:
        prev = self.in_loop
        self.in_loop = True
        self.generic_visit(node)
        self.in_loop = prev

    def visit_Call(self, node: ast.Call) -> Any:
        call_src = ast.unparse(node) if hasattr(ast, "unparse") else ""
        call_name = ""
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr

        # Check 1: float-arithmetic-on-money via float() call
        if call_name == "float" and node.args:
            arg_src = ast.unparse(node.args[0]) if hasattr(ast, "unparse") else ""
            if _is_money_name(arg_src):
                self.violations.append(
                    Violation(
                        check_id="float-arithmetic-on-money",
                        file=self.filename,
                        line=node.lineno,
                        message=f"Converting monetary variable '{arg_src}' to float: money must be integer cents.",
                        hunk=self._get_line_snippet(node.lineno),
                        severity="block",
                    )
                )

        # Check 3: missing-idempotency-key on payment calls
        if any(term in call_name.lower() for term in ["charge", "pay", "process_payment", "gateway"]) or (
            isinstance(node.func, ast.Attribute) and node.func.attr in ["post", "charge"] and "payment" in call_src.lower()
        ):
            # Check keywords or args for idempotency
            kw_names = [kw.arg for kw in node.keywords if kw.arg]
            has_idempotency = any("idempotency" in (k or "").lower() for k in kw_names)
            if not has_idempotency and "idempotency" not in call_src.lower():
                # Avoid false positives on test methods or helper assertions
                is_test = (
                    Path(self.filename).name.startswith("test_")
                    or "tests" in Path(self.filename).parts
                    or (self.current_func or "").startswith("test_")
                )
                if not is_test:
                    self.violations.append(
                        Violation(
                            check_id="missing-idempotency-key",
                            file=self.filename,
                            line=node.lineno,
                            message=f"Payment call '{call_name}' is missing an idempotency key parameter or header.",
                            hunk=self._get_line_snippet(node.lineno),
                            severity="block",
                        )
                    )

        # Check 4: n-plus-one-query
        if self.in_loop:
            if call_name in ["exec", "execute", "query"] or (
                isinstance(node.func, ast.Attribute) and node.func.attr in ["all", "first"] and "select" in call_src
            ):
                self.violations.append(
                    Violation(
                        check_id="n-plus-one-query",
                        file=self.filename,
                        line=node.lineno,
                        message=f"Database query execution '{call_name}' inside loop (N+1 query anti-pattern). Use batching or eager loading.",
                        hunk=self._get_line_snippet(node.lineno),
                        severity="block",
                    )
                )

        # Check 6: pii-logging
        if any(log_call in call_src for log_call in ["logger.", "logging.", "print("]):
            for pii in PII_TERMS:
                if pii in call_src.lower():
                    # Check if masked or scrubbed
                    if not any(safe in call_src.lower() for safe in ["mask", "scrub", "redact", "last4", "hash"]):
                        self.violations.append(
                            Violation(
                                check_id="pii-logging",
                                file=self.filename,
                                line=node.lineno,
                                message=f"Logging sensitive PII or card data '{pii}' without masking or redaction.",
                                hunk=self._get_line_snippet(node.lineno),
                                severity="block",
                            )
                        )
                        break

        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        # Check 1: float-arithmetic-on-money in binary operations (*, /, +, -)
        left_src = ast.unparse(node.left) if hasattr(ast, "unparse") else ""
        right_src = ast.unparse(node.right) if hasattr(ast, "unparse") else ""

        is_left_money = _is_money_name(left_src)
        is_right_money = _is_money_name(right_src)

        is_float_op = False
        # Division produces float in Python 3
        if isinstance(node.op, ast.Div):
            if is_left_money or is_right_money:
                is_float_op = True
        elif isinstance(node.op, (ast.Mult, ast.Add, ast.Sub)):
            # check if one operand is a float constant (e.g. 0.15)
            if (isinstance(node.left, ast.Constant) and isinstance(node.left.value, float)) or (
                isinstance(node.right, ast.Constant) and isinstance(node.right.value, float)
            ):
                if is_left_money or is_right_money:
                    is_float_op = True

        if is_float_op:
            self.violations.append(
                Violation(
                    check_id="float-arithmetic-on-money",
                    file=self.filename,
                    line=node.lineno,
                    message=f"Float arithmetic detected on monetary expression '{ast.unparse(node) if hasattr(ast, 'unparse') else '...'}' (money must be integer cents).",
                    hunk=self._get_line_snippet(node.lineno),
                    severity="block",
                )
            )

        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> Any:
        # Check 2: bare-exception without re-raise around payments or critical blocks
        for handler in node.handlers:
            is_bare = False
            if handler.type is None:
                is_bare = True
            elif isinstance(handler.type, ast.Name) and handler.type.id in ["Exception", "BaseException"]:
                is_bare = True

            if is_bare:
                # check if there is a raise in the handler body
                has_raise = False
                for stmt in handler.body:
                    if isinstance(stmt, ast.Raise):
                        has_raise = True
                        break

                if not has_raise:
                    func_context = (self.current_func or "").lower()
                    file_context = self.filename.lower()
                    if any(k in func_context or k in file_context for k in ["pay", "charge", "checkout", "order", "gateway", "pricing"]):
                        self.violations.append(
                            Violation(
                                check_id="bare-exception",
                                file=self.filename,
                                line=handler.lineno,
                                message="Bare 'except Exception:' without re-raising in payment or checkout logic.",
                                hunk=self._get_line_snippet(handler.lineno),
                                severity="block",
                            )
                        )

        self.generic_visit(node)


def run_static_checks_on_code(code: str, filename: str = "module.py") -> List[Violation]:
    """Run AST and pattern checks on raw Python source code."""
    lines = code.splitlines()
    try:
        tree = ast.parse(code, filename=filename)
    except SyntaxError as e:
        return [
            Violation(
                check_id="syntax-error",
                file=filename,
                line=e.lineno or 1,
                message=f"Syntax error: {e.msg}",
                severity="block",
            )
        ]

    visitor = ScarASTVisitor(filename=filename, lines=lines)
    visitor.visit(tree)
    return visitor.violations


def run_static_checks_on_file(file_path: Path) -> List[Violation]:
    """Run static checks on a single file from the filesystem."""
    if not file_path.exists() or not file_path.suffix == ".py":
        return []
    try:
        content = file_path.read_text(encoding="utf-8")
        return run_static_checks_on_code(content, filename=str(file_path))
    except Exception:
        return []


def run_static_checks_on_diff(diff_text: str) -> List[Violation]:
    """Run static checks on modified code hunks from a unified diff."""
    # Group added lines by file
    violations: List[Violation] = []
    current_file = ""
    current_line = 0
    file_chunks: Dict[str, List[tuple[int, str]]] = {}

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            if current_file not in file_chunks:
                file_chunks[current_file] = []
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            if m:
                current_line = int(m.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file.endswith(".py"):
                file_chunks.setdefault(current_file, []).append((current_line, line[1:]))
            current_line += 1
        elif not line.startswith("-"):
            current_line += 1

    # Check each file's added code chunks
    for filename, lines_with_nums in file_chunks.items():
        if not lines_with_nums:
            continue
        # Check line-by-line pattern rules first
        for lineno, code_line in lines_with_nums:
            # 1. Float math on money
            if any(term in code_line.lower() for term in MONEY_TERMS):
                if re.search(r"\b(float\(|[0-9]+\.[0-9]+|\/)\b", code_line) and not code_line.strip().startswith("#"):
                    # Check if it's float arithmetic on money
                    if any(term in code_line for term in ["price", "cents", "amount", "discount", "total"]):
                        violations.append(
                            Violation(
                                check_id="float-arithmetic-on-money",
                                file=filename,
                                line=lineno,
                                message=f"Float arithmetic on money detected in diff line: {code_line.strip()}",
                                hunk=code_line.strip(),
                                severity="block",
                            )
                        )
            # 2. Bare exception
            if re.search(r"except\s+(Exception|BaseException)?\s*:", code_line):
                violations.append(
                    Violation(
                        check_id="bare-exception",
                        file=filename,
                        line=lineno,
                        message=f"Bare except block introduced in diff line: {code_line.strip()}",
                        hunk=code_line.strip(),
                        severity="block",
                    )
                )
            # 3. Missing idempotency key on charge call
            if any(term in code_line.lower() for term in ["charge(", "pay(", "process_payment("]):
                if "idempotency" not in code_line.lower():
                    violations.append(
                        Violation(
                            check_id="missing-idempotency-key",
                            file=filename,
                            line=lineno,
                            message=f"Payment call without idempotency key in diff line: {code_line.strip()}",
                            hunk=code_line.strip(),
                            severity="block",
                        )
                    )
            # 6. PII logging
            if any(log in code_line for log in ["logger.", "logging.", "print("]):
                for pii in PII_TERMS:
                    if pii in code_line.lower():
                        violations.append(
                            Violation(
                                check_id="pii-logging",
                                file=filename,
                                line=lineno,
                                message=f"PII/card field '{pii}' logged in diff line: {code_line.strip()}",
                                hunk=code_line.strip(),
                                severity="block",
                            )
                        )
                        break

    return violations
