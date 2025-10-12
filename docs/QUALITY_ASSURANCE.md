# Code Quality Assurance

This document describes the code quality tools and processes used in the homelab MCP server project.

## Overview

We use multiple tools to ensure code quality:

- **Ruff** - Fast Python linter and formatter
- **MyPy** - Static type checker
- **Pre-commit hooks** - Automated checks before commits
- **Custom scripts** - Convenient quality check workflows

## Quick Start

### 1. Install Pre-commit Hooks

```bash
uv run pre-commit-install
```

This will run quality checks automatically before each commit.

### 2. Run Quality Checks

```bash
# Quick check (development mode)
uv run qc

# Auto-fix issues
uv run qc-fix

# Strict checking (CI mode)
uv run qc-strict

# All checks with fixes
uv run qc-all
```

## Pre-commit Configuration

We have two pre-commit configurations:

### Development Mode (`.pre-commit-config.yaml`)
- **Auto-fixes** formatting issues
- **Shows** linting warnings but doesn't block commits
- **Allows** commits with type checking issues (warnings only)
- **Focus**: Keep development flow smooth while maintaining basic quality

### Production Mode (`.pre-commit-config-strict.yaml`)
- **Enforces** all quality checks
- **Blocks** commits with any issues
- **Strict** type checking
- **Focus**: Ensure production-ready code quality

## Individual Tools

### Ruff (Linting & Formatting)

```bash
# Format code
uv run format

# Check for linting issues
uv run lint

# Fix auto-fixable issues
uv run ruff check src tests --fix
```

### MyPy (Type Checking)

```bash
# Basic type checking
uv run type-check

# Strict type checking
uv run type-check-strict

# Check specific file
uv run mypy src/homelab_mcp/server.py
```

## Quality Check Scripts

We provide cross-platform scripts for comprehensive quality checking:

### PowerShell (Windows)
```powershell
# Basic checks
.\scripts\quality-check.ps1

# With auto-fix
.\scripts\quality-check.ps1 -Fix

# Strict mode
.\scripts\quality-check.ps1 -Strict

# All checks
.\scripts\quality-check.ps1 -All
```

### Bash (Linux/macOS)
```bash
# Basic checks
./scripts/quality-check.sh

# With auto-fix
./scripts/quality-check.sh --fix

# Strict mode
./scripts/quality-check.sh --strict

# All checks
./scripts/quality-check.sh --all
```

## Development Workflow

### Before Committing

1. **Run auto-fix**: `uv run qc-fix`
2. **Check status**: `uv run qc`
3. **Commit**: Git will run pre-commit hooks automatically

### Before Push/PR

1. **Run strict checks**: `uv run qc-strict`
2. **Ensure all tests pass**: `uv run pytest`
3. **Push/create PR**

### Handling Type Errors

Since we're gradually improving type annotations, MyPy errors are handled differently in development vs. production:

**Development Mode:**
- Type errors show as warnings
- Commits are not blocked
- Focus on new code having proper types

**Production/CI Mode:**
- Type errors block the process
- Must be fixed before merge
- Ensures type safety in production

## Configuration Files

### `.pre-commit-config.yaml`
Development-friendly pre-commit configuration that auto-fixes issues but doesn't block commits for type errors.

### `.pre-commit-config-strict.yaml`
Production-ready configuration that enforces all quality standards.

### `pyproject.toml`
Contains configuration for:
- Ruff linting and formatting rules
- MyPy type checking settings
- Test coverage requirements
- Development script shortcuts

## CI/CD Integration

For continuous integration, use the strict configuration:

```yaml
# In GitHub Actions or similar
- name: Quality Checks
  run: |
    uv run pre-commit run --config .pre-commit-config-strict.yaml --all-files
```

## Troubleshooting

### Pre-commit Hook Issues

```bash
# Reset hooks if having issues
uv run pre-commit uninstall
uv run pre-commit install

# Update hook versions
uv run pre-commit autoupdate
```

### Type Checking Issues

```bash
# See current type errors
uv run type-check

# Check specific files only
uv run mypy src/homelab_mcp/database.py

# Install missing type stubs
uv add types-package-name --dev
```

### Performance Issues

```bash
# Clear pre-commit cache
uv run pre-commit clean

# Run only on changed files
uv run pre-commit run
```

## Best Practices

1. **Run `uv run qc-fix` frequently** to catch issues early
2. **Use type hints on all new code** to gradually improve type safety
3. **Test your changes** with `uv run qc-strict` before creating PRs
4. **Keep commits small** to make quality issues easier to fix
5. **Use the development scripts** for efficient workflows

## Quality Standards

### Code Formatting
- Line length: 88 characters (Black-compatible)
- Auto-formatted with Ruff
- Consistent import sorting

### Type Annotations
- All public functions must have type hints
- Return types required for non-trivial functions
- Gradual migration to full type safety

### Code Quality
- No unused imports or variables
- No debug statements in production code
- Proper error handling
- Clear function and class names

This ensures a high-quality, maintainable codebase while keeping the development experience smooth and productive.
