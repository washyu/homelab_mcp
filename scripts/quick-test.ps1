#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick test script for local development
.DESCRIPTION
    Runs core tests quickly without coverage or integration tests
.PARAMETER Pattern
    Test pattern to match (optional)
.EXAMPLE
    ./scripts/quick-test.ps1
    ./scripts/quick-test.ps1 -Pattern "test_config"
#>
param(
    [string]$Pattern = ""
)

Write-Host "🚀 Running quick tests..." -ForegroundColor Green

# Check if uv is available
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed. Please install it first: https://docs.astral.sh/uv/"
    exit 1
}

# Install dependencies if needed
Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
uv sync --all-extras

# Run linting quickly
Write-Host "🔍 Running linting..." -ForegroundColor Yellow
uv run ruff check src tests --fix
uv run ruff format src tests

# Run tests
Write-Host "🧪 Running tests..." -ForegroundColor Yellow
if ($Pattern) {
    uv run pytest -v -k $Pattern --tb=short -x
} else {
    # Run core tests only for speed
    uv run pytest tests/test_config.py tests/test_error_handling.py tests/test_database.py -v --tb=short -x
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ All tests passed!" -ForegroundColor Green
} else {
    Write-Host "❌ Some tests failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}
