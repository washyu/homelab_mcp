#!/bin/bash
# Quick test script for local development

set -e

PATTERN="${1:-}"

echo "🚀 Running quick tests..."

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first: https://docs.astral.sh/uv/"
    exit 1
fi

# Install dependencies if needed
echo "📦 Installing dependencies..."
uv sync --all-extras

# Run linting quickly
echo "🔍 Running linting..."
uv run ruff check src tests --fix
uv run ruff format src tests

# Run tests
echo "🧪 Running tests..."
if [ -n "$PATTERN" ]; then
    uv run pytest -v -k "$PATTERN" --tb=short -x
else
    # Run core tests only for speed
    uv run pytest tests/test_config.py tests/test_error_handling.py tests/test_database.py -v --tb=short -x
fi

echo "✅ All tests passed!"