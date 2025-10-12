#!/usr/bin/env pwsh
# Quality check script for development and CI

param(
    [switch]$Strict,
    [switch]$Fix,
    [switch]$TypeCheck,
    [switch]$All
)

Write-Host "[QC] Running code quality checks..." -ForegroundColor Blue

# Set error handling
$ErrorActionPreference = "Continue"
$exitCode = 0

if ($Fix -or $All) {
    Write-Host "`n[FORMAT] Running Ruff formatter..." -ForegroundColor Yellow
    uv run ruff format src tests
    if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }

    Write-Host "`n[LINT] Running Ruff linter with auto-fix..." -ForegroundColor Yellow
    uv run ruff check src tests --fix
    if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
}

if ($TypeCheck -or $All -or $Strict) {
    Write-Host "`n[TYPE] Running MyPy type checking..." -ForegroundColor Yellow
    if ($Strict) {
        uv run mypy src --strict --ignore-missing-imports --show-error-codes
    } else {
        uv run mypy src --ignore-missing-imports --show-error-codes
    }
    $mypyExit = $LASTEXITCODE

    if ($Strict -and $mypyExit -ne 0) {
        $exitCode = $mypyExit
        Write-Host "[ERROR] MyPy type checking failed in strict mode" -ForegroundColor Red
    } elseif ($mypyExit -ne 0) {
        Write-Host "[WARNING] MyPy found type issues (non-blocking in development)" -ForegroundColor Yellow
    } else {
        Write-Host "[SUCCESS] MyPy type checking passed" -ForegroundColor Green
    }
}

if (-not ($Fix -or $TypeCheck)) {
    # Default: just run basic checks
    Write-Host "`n[LINT] Running Ruff linter..." -ForegroundColor Yellow
    uv run ruff check src tests
    if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
}

# Run pre-commit hooks if available
if (Test-Path ".pre-commit-config.yaml") {
    if ($Strict) {
        Write-Host "`n[STRICT] Running strict pre-commit checks..." -ForegroundColor Yellow
        if (Test-Path ".pre-commit-config-strict.yaml") {
            uv run pre-commit run --config .pre-commit-config-strict.yaml --all-files
        } else {
            uv run pre-commit run --all-files
        }
        if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
    } else {
        Write-Host "`n[DEV] Running development pre-commit checks..." -ForegroundColor Yellow
        uv run pre-commit run --all-files
        # Don't fail on pre-commit issues in development mode
    }
}

# Summary
Write-Host "`n" + ("="*50) -ForegroundColor Blue
if ($exitCode -eq 0) {
    Write-Host "[SUCCESS] All quality checks passed!" -ForegroundColor Green
    if (-not $Strict) {
        Write-Host "[INFO] Run with -Strict flag for production-ready checks" -ForegroundColor Cyan
    }
} else {
    Write-Host "[ERROR] Some quality checks failed (exit code: $exitCode)" -ForegroundColor Red
    Write-Host "[INFO] Run with -Fix flag to auto-fix issues" -ForegroundColor Cyan
}
Write-Host ("="*50) -ForegroundColor Blue

exit $exitCode
