#!/bin/bash
# Quality check script for development and CI

set -e

# Colors
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
STRICT=false
FIX=false
TYPECHECK=false
ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --strict)
            STRICT=true
            shift
            ;;
        --fix)
            FIX=true
            shift
            ;;
        --type-check)
            TYPECHECK=true
            shift
            ;;
        --all)
            ALL=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--strict] [--fix] [--type-check] [--all]"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🔍 Running code quality checks...${NC}"

exit_code=0

if [[ "$FIX" == "true" || "$ALL" == "true" ]]; then
    echo -e "\n${YELLOW}📝 Running Ruff formatter...${NC}"
    uv run ruff format src tests || exit_code=$?

    echo -e "\n${YELLOW}🔧 Running Ruff linter with auto-fix...${NC}"
    uv run ruff check src tests --fix || exit_code=$?
fi

if [[ "$TYPECHECK" == "true" || "$ALL" == "true" || "$STRICT" == "true" ]]; then
    echo -e "\n${YELLOW}🔍 Running MyPy type checking...${NC}"
    if [[ "$STRICT" == "true" ]]; then
        if uv run mypy src --strict --ignore-missing-imports --show-error-codes; then
            echo -e "${GREEN}✅ MyPy type checking passed${NC}"
        else
            mypy_exit=$?
            exit_code=$mypy_exit
            echo -e "${RED}❌ MyPy type checking failed in strict mode${NC}"
        fi
    else
        if uv run mypy src --ignore-missing-imports --show-error-codes; then
            echo -e "${GREEN}✅ MyPy type checking passed${NC}"
        else
            echo -e "${YELLOW}⚠️  MyPy found type issues (non-blocking in development)${NC}"
        fi
    fi
fi

if [[ "$FIX" != "true" && "$TYPECHECK" != "true" ]]; then
    # Default: just run basic checks
    echo -e "\n${YELLOW}🔧 Running Ruff linter...${NC}"
    uv run ruff check src tests || exit_code=$?
fi

# Run pre-commit hooks if available
if [[ -f ".pre-commit-config.yaml" ]]; then
    if [[ "$STRICT" == "true" ]]; then
        echo -e "\n${YELLOW}🔒 Running strict pre-commit checks...${NC}"
        if [[ -f ".pre-commit-config-strict.yaml" ]]; then
            uv run pre-commit run --config .pre-commit-config-strict.yaml --all-files || exit_code=$?
        else
            uv run pre-commit run --all-files || exit_code=$?
        fi
    else
        echo -e "\n${YELLOW}🔄 Running development pre-commit checks...${NC}"
        uv run pre-commit run --all-files || true  # Don't fail in development mode
    fi
fi

# Summary
echo -e "\n${BLUE}==================================================${NC}"
if [[ $exit_code -eq 0 ]]; then
    echo -e "${GREEN}✅ All quality checks passed!${NC}"
    if [[ "$STRICT" != "true" ]]; then
        echo -e "${CYAN}💡 Run with --strict flag for production-ready checks${NC}"
    fi
else
    echo -e "${RED}❌ Some quality checks failed (exit code: $exit_code)${NC}"
    echo -e "${CYAN}💡 Run with --fix flag to auto-fix issues${NC}"
fi
echo -e "${BLUE}==================================================${NC}"

exit $exit_code
