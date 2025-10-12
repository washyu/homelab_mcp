# CI/CD Test Strategy for Homelab MCP Server

## Current Test Status Analysis

### ✅ **CI/CD Ready Tests (248 passing)**
- **Unit Tests**: All core business logic
- **Configuration Tests**: 100% coverage ✅
- **Database Tests**: SQLite operations ✅
- **Error Handling Tests**: 99% coverage ✅
- **SSH Tools Tests**: Basic functionality ✅
- **VM Operations Tests**: Core VM management ✅
- **Migration Tests**: 93% coverage ✅

### ⚠️ **Tests That Need CI/CD Adaptation (13 failing)**

#### **Category 1: Integration Tests (7 failing)**
- **Issue**: Require real network connectivity
- **CI/CD Impact**: Will always fail in isolated CI environments
- **Solution**: Mock network dependencies or mark as integration-only

#### **Category 2: Ansible Service Tests (4 failing)**
- **Issue**: Tests expect real Ansible execution
- **CI/CD Impact**: Need proper mocking or Ansible installation
- **Solution**: Enhanced mocking or containerized testing

#### **Category 3: Migration Hash Tests (2 failing)**
- **Issue**: Hash mocking inconsistencies
- **CI/CD Impact**: Minor, easily fixable

## Recommendations for CI/CD Pipeline

### **Priority 1: Fix Critical CI/CD Blockers** 🚨

#### **1. Fix Remaining Unit Test Issues**
```python
# Fix these 2 migration tests:
- test_migrate_device_history_success (hash mocking)
- test_full_migration_workflow_with_mocks (verification)
```

#### **2. Fix Ansible Service Tests**
```python
# These 4 tests need proper mocking:
- test_ansible_playbook_execution_success
- test_ansible_playbook_execution_failure
- test_ansible_variable_substitution
- test_ansible_template_rendering
```

### **Priority 2: Increase Coverage for Core Modules** 📊

#### **Critical Coverage Gaps** (Target for CI/CD)
| Module | Current | Target | Missing Lines |
|--------|---------|--------|---------------|
| `service_installer.py` | 28% | **60%** | 353 lines |
| `infrastructure_crud.py` | 32% | **50%** | 375 lines |
| `server.py` | 43% | **60%** | 76 lines |
| `database.py` | 50% | **70%** | 116 lines |

### **Priority 3: CI/CD Pipeline Configuration** ⚙️

#### **Test Categories for CI/CD**

1. **Unit Tests** (Fast, always run)
   - Core business logic
   - Configuration management
   - Error handling
   - Database operations (SQLite only)

2. **Integration Tests** (Slower, conditional)
   - Mock-based integration tests
   - Cross-module interaction tests
   - Service installer tests (mocked)

3. **End-to-End Tests** (Slowest, optional)
   - Full-stack integration (requires infrastructure)
   - Real network operations
   - Docker/container tests

## CI/CD Implementation Plan

### **Phase 1: Immediate (This Sprint)**

#### **A. Fix Unit Test Failures** ⭐
- Fix 2 migration hash tests
- Fix 4 Ansible service tests
- **Goal**: 100% unit test pass rate

#### **B. Separate Test Categories**
```bash
# Unit tests (fast, always run)
pytest tests/ -m "not integration and not e2e"

# Integration tests (with mocking)
pytest tests/ -m "integration and not e2e"

# End-to-end tests (real infrastructure required)
pytest tests/ -m "e2e"
```

### **Phase 2: Coverage Improvements (Next Sprint)**

#### **A. Service Installer Tests** (28% → 60%)
- Add tests for Docker Compose service installation
- Add tests for script-based installations
- Add tests for Terraform service deployment
- Add error handling tests

#### **B. Infrastructure CRUD Tests** (32% → 50%)
- Add tests for device configuration updates
- Add tests for backup/restore operations
- Add tests for scaling services
- Add validation tests

#### **C. Server Tests** (43% → 60%)
- Add MCP protocol tests
- Add tool execution tests
- Add health endpoint tests
- Add error response tests

### **Phase 3: Enhanced Testing (Future Sprint)**

#### **A. Database Tests** (50% → 70%)
- Add PostgreSQL adapter tests (mocked)
- Add migration tests
- Add performance tests
- Add connection pooling tests

#### **B. End-to-End Testing Infrastructure**
- Docker Compose test environment
- Mock SSH servers for testing
- Containerized integration tests
- Performance benchmarking

## GitHub Actions CI/CD Workflow

### **Recommended Workflow Structure**

```yaml
name: CI/CD Pipeline

on: [push, pull_request]

jobs:
  # Fast unit tests (required to pass)
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      - name: Run unit tests
        run: |
          uv run pytest tests/ -m "not integration and not e2e" --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  # Integration tests (allowed to fail, but tracked)
  integration-tests:
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      - name: Run integration tests
        run: |
          uv run pytest tests/ -m "integration and not e2e" --tb=short

  # Multi-platform testing
  cross-platform:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.11', '3.12']
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      - name: Run core tests
        run: |
          uv run pytest tests/test_config.py tests/test_error_handling.py tests/test_database.py -v
```

## Test Quality Gates for CI/CD

### **Required to Pass** ✅
- Unit tests: 100% pass rate
- Core module coverage: >50%
- No critical security issues
- Code formatting (black, flake8)
- Type checking (mypy)

### **Warning but Allow** ⚠️
- Integration test failures
- Coverage below 70% (tracked but not blocking)
- Performance regression <20%

### **Informational** ℹ️
- End-to-end test results
- Performance benchmarks
- Security scan results

## Next Steps

### **Immediate Actions** (This Week)
1. **Fix the 6 remaining unit test failures**
2. **Add test markers for categorization**
3. **Create basic GitHub Actions workflow**
4. **Set up coverage reporting**

### **Short Term** (Next 2 Weeks)
1. **Improve service_installer.py coverage to 60%**
2. **Add infrastructure_crud.py tests**
3. **Enhance server.py test coverage**
4. **Set up cross-platform testing**

### **Medium Term** (Next Month)
1. **Implement containerized integration testing**
2. **Add performance benchmarking**
3. **Set up automated security scanning**
4. **Create end-to-end test environments**

## Success Metrics

- **Unit Test Pass Rate**: 100%
- **Overall Coverage**: >60%
- **CI/CD Pipeline Reliability**: >95%
- **Cross-Platform Compatibility**: Windows, macOS, Linux
- **Documentation Coverage**: All public APIs tested

This strategy will give you a robust, CI/CD-ready test suite that can scale with your project while maintaining reliability and performance.
