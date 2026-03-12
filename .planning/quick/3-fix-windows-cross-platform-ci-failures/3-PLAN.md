---
phase: quick
plan: 3
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/main.yml
  - pyproject.toml
autonomous: true
requirements: [QUICK-3]

must_haves:
  truths:
    - "The cross-platform CI job completes without PowerShell line-continuation errors"
    - "pytest does not wander into uv cache directories on Windows runners"
  artifacts:
    - path: ".github/workflows/main.yml"
      provides: "Fixed cross-platform pytest invocation (single line, no backslash)"
    - path: "pyproject.toml"
      provides: "norecursedirs setting that excludes temp/cache paths from collection"
  key_links:
    - from: ".github/workflows/main.yml"
      to: "pytest"
      via: "uv run pytest tests/test_config.py ... -v --tb=short (single line)"
      pattern: "uv run pytest.*-v --tb=short"
---

<objective>
Fix two bugs causing the Windows cross-platform CI job to fail.

Bug 1: The `cross-platform` job's "Run core tests" step uses a bash backslash `\` for
line continuation. PowerShell does not support `\` as a line continuation character —
it treats `-v` as a separate command, producing "The term '-v' is not recognized".

Bug 2: pytest traverses the uv cache at `D:\a\_temp\setup-uv-cache\...` on Windows
runners and tries to collect `win32comext\taskscheduler\test\test_addtask.py`, causing
a Windows fatal access violation. Adding `norecursedirs` patterns in pyproject.toml
prevents pytest from descending into those directories.

Purpose: Make the cross-platform CI matrix succeed on Windows without errors.
Output: Updated workflow file (single-line pytest command) and updated pyproject.toml
(norecursedirs covering temp/cache/site-packages paths).
</objective>

<execution_context>
@/home/shaun/.claude/get-shit-done/workflows/execute-plan.md
@/home/shaun/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.github/workflows/main.yml
@pyproject.toml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Collapse cross-platform pytest command onto a single line</name>
  <files>.github/workflows/main.yml</files>
  <action>
    In the `cross-platform` job, find the "Run core tests" step (currently lines 149-152).
    Replace the multi-line backslash-continued command:

    ```yaml
    - name: Run core tests
      run: |
        uv run pytest tests/test_config.py tests/test_error_handling.py tests/test_database.py \
          -v --tb=short
    ```

    with a single-line command (no backslash, no indented continuation):

    ```yaml
    - name: Run core tests
      run: uv run pytest tests/test_config.py tests/test_error_handling.py tests/test_database.py -v --tb=short
    ```

    The `run: |` block-scalar form is not needed when there is only one line; use the
    inline `run: <command>` form to make it unambiguous across shells.

    Do not change any other part of the workflow file.
  </action>
  <verify>
    <automated>grep -n "run: uv run pytest tests/test_config" /home/shaun/projects/mcp_python_server/.github/workflows/main.yml</automated>
  </verify>
  <done>The "Run core tests" step is a single line with no backslash continuation. grep confirms the pattern appears on one line.</done>
</task>

<task type="auto">
  <name>Task 2: Add norecursedirs to prevent pytest traversing uv cache on Windows</name>
  <files>pyproject.toml</files>
  <action>
    In `pyproject.toml` under `[tool.pytest.ini_options]`, add a `norecursedirs` list
    after the existing `testpaths` line. Insert:

    ```toml
    norecursedirs = [
        ".git",
        ".hg",
        ".mypy_cache",
        ".tox",
        ".venv",
        "venv",
        "_build",
        "buck-out",
        "build",
        "dist",
        "node_modules",
        "*.egg",
        "__pycache__",
        ".uv",
        "setup-uv-cache",
        "_temp",
    ]
    ```

    The critical entries are `setup-uv-cache` and `_temp` which match the Windows runner
    uv cache path `D:\a\_temp\setup-uv-cache\...`. The others are conventional exclusions
    that prevent similar issues in other environments.

    `testpaths = ["tests"]` already exists and restricts the default collection root, but
    `norecursedirs` adds a belt-and-suspenders guard for any path that appears as a
    command-line argument or conftest discovery traversal.

    Do not change any other section of pyproject.toml.
  </action>
  <verify>
    <automated>cd /home/shaun/projects/mcp_python_server && uv run pytest tests/test_config.py tests/test_error_handling.py tests/test_database.py -v --tb=short --co -q 2>&1 | tail -5</automated>
  </verify>
  <done>
    pyproject.toml contains `norecursedirs` with `setup-uv-cache` and `_temp` entries.
    Local `--co` (collect-only) dry-run exits 0 and lists only tests under `tests/`.
  </done>
</task>

</tasks>

<verification>
After both tasks complete:

1. Confirm workflow fix: `grep -n "run: uv run pytest" .github/workflows/main.yml` — the
   cross-platform step must appear as a single `run:` line with no `|` block scalar.

2. Confirm pyproject.toml fix: `grep -A5 "norecursedirs" pyproject.toml` — must show
   `setup-uv-cache` and `_temp` in the list.

3. Smoke test locally: `uv run pytest tests/test_config.py tests/test_error_handling.py tests/test_database.py -v --tb=short`
   must pass (same command the Windows runner will execute).
</verification>

<success_criteria>
- `.github/workflows/main.yml` cross-platform "Run core tests" step uses single-line `run:` with no backslash
- `pyproject.toml` `[tool.pytest.ini_options]` includes `norecursedirs` with cache/temp exclusions
- Local smoke test of the three test files passes without collection errors
</success_criteria>

<output>
After completion, create `.planning/quick/3-fix-windows-cross-platform-ci-failures/3-SUMMARY.md`
</output>
