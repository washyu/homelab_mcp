---
phase: quick-2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: []
autonomous: true
requirements: [QUICK-2]
must_haves:
  truths:
    - "All pre-commit hooks pass against all files"
    - "No ruff lint violations remain in src/ or tests/"
    - "No ruff format violations remain in src/ or tests/"
    - "No mypy type errors remain in src/"
    - "No trailing whitespace, missing newlines, or YAML/JSON/TOML parse errors"
  artifacts: []
  key_links: []
---

<objective>
Run the full pre-commit hook suite against every file in the repository, fix all
auto-fixable issues, then address any remaining issues that require manual edits
until all hooks pass cleanly.

Purpose: Ensure the codebase is clean before pushing to remote — CI will run the
same checks and a passing local run guarantees CI passes.
Output: A clean working tree where `pre-commit run --all-files` exits 0.
</objective>

<execution_context>
@/home/shaun/.claude/get-shit-done/workflows/execute-plan.md
@/home/shaun/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Run pre-commit against all files and collect failures</name>
  <files>any files flagged by hooks</files>
  <action>
    Run the standard pre-commit config against every tracked file:

        cd /home/shaun/projects/mcp_python_server
        uv run pre-commit run --all-files 2>&1

    Record which hooks fail and which files are flagged. Several hooks auto-fix
    in place (ruff --fix, ruff-format, end-of-file-fixer, trailing-whitespace).
    After the first run, immediately re-run to confirm auto-fixes resolved those
    hooks:

        uv run pre-commit run --all-files 2>&1

    If the second run exits 0, task is complete — move to Task 2.
  </action>
  <verify>
    <automated>cd /home/shaun/projects/mcp_python_server && uv run pre-commit run --all-files 2>&1; echo "Exit: $?"</automated>
  </verify>
  <done>Second pre-commit run exits 0 OR a list of remaining manual failures is identified for Task 2.</done>
</task>

<task type="auto">
  <name>Task 2: Fix remaining failures and verify clean run</name>
  <files>any files still flagged after Task 1</files>
  <action>
    For each hook that still fails after the auto-fix pass, apply manual fixes:

    **mypy errors** — resolve type annotation issues in src/homelab_mcp/:
    - Missing return types: add the correct return type annotation
    - Incompatible types: correct the annotation or add an explicit cast
    - Missing Optional: use `X | None` syntax (Python 3.12+)
    - Run `uv run mypy src/` to verify mypy-only before full suite

    **ruff lint errors that --fix could not auto-resolve** — common patterns:
    - Unused imports (F401): remove or add to `__all__`
    - Complexity issues: refactor as minimally as possible
    - Run `uv run ruff check src/ tests/` to target ruff-only

    **check-yaml / check-json / check-toml** — parse errors in config files:
    - Open the flagged file and fix the syntax error
    - YAML: indentation, missing quotes around special chars
    - TOML: invalid key format

    **check-ast** — Python syntax errors:
    - Open the flagged file and fix the syntax

    After all manual edits, run the full suite one final time:

        cd /home/shaun/projects/mcp_python_server
        uv run pre-commit run --all-files 2>&1

    If it exits 0, stage all modified files and commit:

        git add -u
        git commit -m "chore: fix pre-commit hook violations"

    If it still fails, iterate — fix remaining flagged files and re-run until
    the suite exits 0.
  </action>
  <verify>
    <automated>cd /home/shaun/projects/mcp_python_server && uv run pre-commit run --all-files; echo "Exit: $?"</automated>
  </verify>
  <done>`pre-commit run --all-files` exits 0 and all changes are committed.</done>
</task>

</tasks>

<verification>
Final check — all three quality tools agree the codebase is clean:

    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/
    uv run mypy src/
    uv run pre-commit run --all-files

All commands exit 0 with no errors reported.
</verification>

<success_criteria>
- `pre-commit run --all-files` exits 0
- No uncommitted modified files remain (git status is clean)
- The codebase is ready to push to remote without CI failures
</success_criteria>

<output>
After completion, create `.planning/quick/2-run-all-pre-commit-checks-before-push/2-SUMMARY.md`
</output>
