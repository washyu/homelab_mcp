# TESTING - Framework, Structure & Patterns

## Framework & Configuration

- **Framework**: pytest 8.3.5+ with pytest-asyncio
- **Config files**: `pyproject.toml` ([tool.pytest.ini_options]) and `pytest.ini`
- **Coverage**: src/ with term-missing, HTML (`htmlcov/`), and XML (`coverage.xml`) reports
- **Strict mode**: `--strict-markers`, `--strict-config` enabled

### Key Commands
```bash
uv run pytest                                    # All tests
uv run pytest tests/ -m "not integration"        # Unit tests only (fast)
uv run pytest tests/integration/ -m integration  # Integration tests (Docker required)
uv run pytest tests/test_server.py -v            # Specific file
```

### Markers
```python
markers = [
    "unit",        # Unit tests
    "integration", # Integration tests (Docker required)
    "slow",        # Slow tests
    "network",     # Tests requiring network access
    "ssh",         # Tests requiring SSH connectivity
    "database",    # Tests requiring database
    "ansible",     # Tests requiring Ansible
    "vm",          # Tests for VM operations
]
```

## Test Organization

### Unit Tests (20 files, ~9K LOC, 386 test functions)
Located in `tests/test_*.py`, no external dependencies required.

| File | Covers |
|------|--------|
| `test_tools.py` | Tool registry and execution |
| `test_ssh_tools.py` | SSH discovery and operations |
| `test_database.py` | Database adapter operations |
| `test_error_handling.py` | Timeout/retry decorators |
| `test_server.py` | MCP server protocol |
| `test_service_installer.py` | Service installation logic |
| `test_infrastructure_crud.py` | Infrastructure lifecycle |
| `test_vm_operations.py` | VM management |
| `test_config.py` | Configuration management |
| `test_migration.py` | Database migrations |
| `test_sitemap.py` | Network topology |
| `test_http_transport.py` | HTTP transport layer |
| `test_ssh_credentials.py` | SSH credential management |
| `test_proxmox_api.py` | Proxmox API client |
| `test_ansible.py` | Ansible integration |

### Integration Tests (4 files in `tests/integration/`)
Require Docker containers. Setup managed by `conftest.py` and `docker_client_factory.py`.

| File | Covers |
|------|--------|
| `test_ssh_integration.py` | Real SSH connections |
| `test_full_stack_integration.py` | End-to-end workflows |
| `test_sitemap_integration.py` | Network discovery |
| `test_proxmox_integration.py` | Proxmox API calls |

## Mocking Patterns

### Pattern 1: @patch decorator (most common, 604+ occurrences)
```python
@patch("src.homelab_mcp.ssh_tools.asyncssh.connect")
async def test_ssh_discover_success(mock_connect):
    mock_conn = AsyncMock()
    mock_connect.return_value = mock_conn
    # ...
```

### Pattern 2: AsyncMock for async functions
```python
mock_conn = AsyncMock()
mock_conn.run = AsyncMock(return_value=MagicMock(exit_status=0, stdout="output"))
```

### Pattern 3: Custom mock classes
```python
class MockAnsibleRunner:
    def __init__(self, success=True):
        self.success = success
    async def run(self, playbook, inventory):
        return {"status": "ok" if self.success else "failed"}
```

### Pattern 4: Context manager patches (multiple simultaneous mocks)
```python
with patch("module.function") as mock_func:
    with patch.object(self.installer, "check_service_requirements") as mock_check:
        # Multiple patches in one test
```

### Pattern 5: Monkeypatch via fixture
```python
@pytest.fixture
def docker_client():
    from .docker_client_factory import get_docker_client_or_skip
    return get_docker_client_or_skip()
```

## Fixtures

### Unit Test Fixtures
```python
@pytest.fixture
def adapter(self, temp_db):
    adapter = SQLiteAdapter(temp_db)
    adapter.init_schema()
    return adapter

@pytest.fixture
def temp_db(self):
    yield ":memory:"
```

### Integration Test Fixtures (`tests/integration/conftest.py`)
```python
@pytest.fixture(scope="session")
def docker_client():
    """Docker client for test containers."""

@pytest.fixture(scope="session")
def test_container(docker_client):
    """Start Ubuntu container, wait for SSH readiness."""
    # Returns: {hostname, port 2222, admin_user, admin_pass, test_user, test_pass}

@pytest.fixture
def clean_container(test_container):
    """Clean state: kill mcp_admin processes, remove user/keys."""

@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests."""
```

## Coverage Configuration

```toml
# pyproject.toml
[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "@abstractmethod",
]
```

## Coverage Gaps

### Well Covered
- SSH tools and discovery (extensive mocking)
- Database operations (in-memory SQLite)
- Error handling decorators
- Service installation logic
- Tool execution paths

### Less Covered
- Script-based service installation (stub - raises "not yet implemented")
- Some Proxmox integration edge cases
- WebSocket shell sessions
- Infrastructure CRUD edge cases
- Stub functions in `infrastructure_crud.py`
