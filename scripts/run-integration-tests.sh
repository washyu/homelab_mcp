#!/bin/bash

# Script to run integration tests with Docker setup

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🐳 Starting integration test setup..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose > /dev/null 2>&1; then
    echo "❌ docker-compose is not installed. Please install docker-compose and try again."
    exit 1
fi

# Clean up any existing containers
echo "🧹 Cleaning up existing test containers..."
docker-compose -f docker-compose.test.yml down -v --remove-orphans 2>/dev/null || true

# Install test dependencies if needed
echo "📦 Installing test dependencies..."
pip3 install pytest pytest-asyncio docker

# Run integration tests
echo "🚀 Running integration tests..."
python3 -m pytest tests/integration/ -v -s "$@"

# Cleanup
echo "🧹 Cleaning up test containers..."
docker-compose -f docker-compose.test.yml down -v --remove-orphans

echo "✅ Integration tests completed!"
