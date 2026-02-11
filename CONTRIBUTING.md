# Contributing to Homelab MCP Server

Thank you for your interest in contributing to the Homelab MCP Server! This document provides guidelines and instructions for contributing.

## 🚀 Quick Start

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/homelab_mcp.git
   cd homelab_mcp
   ```
3. **Install dependencies** using uv:
   ```bash
   # Install uv if you haven't already
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install dependencies
   uv sync
   ```

## 📋 Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Your Changes

Follow these guidelines:
- Write clear, descriptive commit messages
- Add tests for new functionality
- Update documentation as needed
- Follow the existing code style

### 3. Run Tests and Quality Checks

Before submitting, ensure all checks pass:

```bash
# Run unit tests
uv run pytest -v -m "not integration"

# Run linting
uv run ruff check src tests

# Run formatting check
uv run ruff format --check src tests

# Run type checking
uv run mypy src --ignore-missing-imports

# Or run everything at once
./scripts/quality-check.sh
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: add new feature description"
# or
git commit -m "fix: resolve bug description"
```

**Commit message format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear title describing the change
- Description of what changed and why
- Link to any related issues
- Screenshots/examples if applicable

## 🧪 Testing Guidelines

### Unit Tests
- **Required** for all new functionality
- Tests should be fast and isolated
- Use mocking for external dependencies
- Aim for >80% coverage on new code

```bash
# Run unit tests only
uv run pytest tests/ -m "not integration" -v

# Run specific test file
uv run pytest tests/test_your_file.py -v

# Run with coverage
uv run pytest --cov=src --cov-report=term-missing
```

### Integration Tests
- Optional but encouraged for complex features
- Require Docker for container operations
- Run manually or in CI on schedule

```bash
# Run integration tests
uv run pytest tests/integration/ -m integration -v
```

## 📝 Code Style

We use **ruff** for linting and formatting:

- **Line length**: 120 characters
- **Python version**: 3.12+
- **Type hints**: Required for all functions
- **Async**: Use async/await for I/O operations

### Auto-format your code:
```bash
uv run ruff format src tests
uv run ruff check --fix src tests
```

### Type checking:
```bash
uv run mypy src --ignore-missing-imports
```

## 🏗️ Project Structure

```
src/homelab_mcp/
├── server.py              # MCP server entry point
├── tools.py               # Tool registry (49 tools)
├── tool_handlers/         # Tool implementation handlers
├── tool_schemas/          # JSON schemas for tools
├── ssh_tools.py           # SSH discovery & operations
├── service_installer.py   # Service installation framework
├── infrastructure_crud.py # Infrastructure lifecycle
├── vm_operations.py       # VM/container management
├── proxmox_api.py         # Proxmox VE API integration
├── database.py            # SQLite database operations
└── config.py              # Configuration management

tests/
├── test_*.py              # Unit tests
└── integration/           # Integration tests
    └── test_*_integration.py
```

## 🎯 Areas for Contribution

### High Priority
- **Service Templates**: Add new service definitions (Jellyfin, Nextcloud, etc.)
- **Test Coverage**: Improve coverage for `service_installer.py` (27%), `infrastructure_crud.py` (31%)
- **Documentation**: Add examples, tutorials, troubleshooting guides
- **Bug Fixes**: Check [open issues](https://github.com/washyu/homelab_mcp/issues)

### Feature Ideas
- New MCP tools for infrastructure management
- Enhanced Proxmox integration
- Additional VM platform support (VMware, VirtualBox)
- Web UI for monitoring (see issue #17)
- Service registry for tracking installations (see issue #19)

## 🐛 Reporting Bugs

When reporting bugs, please include:
1. **Description**: Clear description of the issue
2. **Steps to reproduce**: Detailed steps to reproduce the behavior
3. **Expected behavior**: What you expected to happen
4. **Actual behavior**: What actually happened
5. **Environment**: OS, Python version, uv version
6. **Logs**: Relevant error messages or logs

## 💡 Suggesting Features

Feature requests are welcome! Please:
1. Check if the feature already exists or is planned
2. Describe the use case and problem it solves
3. Provide examples of how it would work
4. Consider implementation complexity

## 📜 Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Follow the project's coding standards

## 🔐 Security

If you discover a security vulnerability, please email the maintainer directly instead of opening a public issue. See SECURITY.md for details.

## ❓ Questions?

- **Documentation**: Check [README.md](README.md) and [CLAUDE.md](CLAUDE.md)
- **Issues**: Search [existing issues](https://github.com/washyu/homelab_mcp/issues)
- **Discussions**: Start a [GitHub Discussion](https://github.com/washyu/homelab_mcp/discussions)

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to Homelab MCP Server!** 🎉
