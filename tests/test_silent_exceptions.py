"""AST-based regression test to detect silent exception handlers.

Scans all Python files in src/homelab_mcp/ for except clauses where the
body is only `pass` (no logging, no raise, no assignment). Silent exception
handlers mask real errors and make debugging impossible.
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple


class Violation(NamedTuple):
    """A silent exception handler found in the codebase."""

    file: str
    line: int
    exception_type: str


def _is_pass_only_body(body: list[ast.stmt]) -> bool:
    """Check if an exception handler body is only `pass` or `...`."""
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        if stmt.value.value is Ellipsis:
            return True
    return False


def _get_exception_type_name(node: ast.ExceptHandler) -> str:
    """Extract the exception type name from an ExceptHandler node."""
    if node.type is None:
        return "bare except"
    if isinstance(node.type, ast.Name):
        return node.type.id
    if isinstance(node.type, ast.Attribute):
        parts = []
        current = node.type
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    if isinstance(node.type, ast.Tuple):
        names = []
        for elt in node.type.elts:
            if isinstance(elt, ast.Name):
                names.append(elt.id)
            elif isinstance(elt, ast.Attribute):
                names.append(ast.dump(elt))
        return f"({', '.join(names)})"
    return "unknown"


def _is_import_error_handler(node: ast.ExceptHandler) -> bool:
    """Check if handler catches ImportError (import fallback pattern)."""
    if node.type is None:
        return False
    if isinstance(node.type, ast.Name) and node.type.id == "ImportError":
        return True
    if isinstance(node.type, ast.Tuple):
        for elt in node.type.elts:
            if isinstance(elt, ast.Name) and elt.id == "ImportError":
                return True
    return False


def _is_cancelled_error_handler(node: ast.ExceptHandler) -> bool:
    """Check if handler catches asyncio.CancelledError."""
    if node.type is None:
        return False
    if isinstance(node.type, ast.Attribute):
        if isinstance(node.type.value, ast.Name):
            if node.type.value.id == "asyncio" and node.type.attr == "CancelledError":
                return True
    if isinstance(node.type, ast.Name) and node.type.id == "CancelledError":
        return True
    return False


def find_silent_exception_handlers(source_dir: Path) -> list[Violation]:
    """Scan all .py files for silent exception handlers (except: pass)."""
    violations: list[Violation] = []

    for py_file in sorted(source_dir.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue

            if not _is_pass_only_body(node.body):
                continue

            # Skip acceptable patterns
            if _is_import_error_handler(node):
                continue
            if _is_cancelled_error_handler(node):
                continue

            exception_type = _get_exception_type_name(node)
            violations.append(
                Violation(
                    file=str(py_file),
                    line=node.lineno,
                    exception_type=exception_type,
                )
            )

    return violations


def test_no_silent_exception_handlers() -> None:
    """Ensure no silent exception handlers (except: pass) exist in production code.

    Silent exception handlers swallow errors and make debugging impossible.
    All exception handlers must either:
    - Log the exception (logger.debug/warning/error)
    - Re-raise the exception
    - Perform meaningful error handling

    Acceptable exceptions:
    - except ImportError: pass (import fallbacks)
    - except asyncio.CancelledError: pass (cancellation cleanup)
    """
    src_dir = Path(__file__).parent.parent / "src" / "homelab_mcp"
    assert src_dir.exists(), f"Source directory not found: {src_dir}"

    violations = find_silent_exception_handlers(src_dir)

    if violations:
        report_lines = ["Silent exception handlers found (except: pass):"]
        for v in violations:
            # Make path relative for readability
            rel_path = Path(v.file).relative_to(Path(__file__).parent.parent)
            report_lines.append(f"  {rel_path}:{v.line} - except {v.exception_type}: pass")
        report_lines.append(
            f"\nTotal: {len(violations)} silent handler(s). "
            "Replace 'pass' with logging (logger.debug/warning) or meaningful handling."
        )
        pytest_msg = "\n".join(report_lines)
        raise AssertionError(pytest_msg)


if __name__ == "__main__":
    src_dir = Path(__file__).parent.parent / "src" / "homelab_mcp"
    violations = find_silent_exception_handlers(src_dir)
    if violations:
        print(f"Found {len(violations)} silent exception handler(s):")
        for v in violations:
            print(f"  {v.file}:{v.line} - except {v.exception_type}: pass")
        sys.exit(1)
    else:
        print("No silent exception handlers found.")
