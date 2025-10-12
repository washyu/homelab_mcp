# CI/CD Workflows

This project uses a single, efficient GitHub Actions workflow that adapts based on the context and triggers.

## Main Workflow (`main.yml`)

### Always Runs
- **Unit tests + Code quality** - Fast feedback on every push/PR
- **Coverage reporting** - Tracks test coverage via Codecov
- **Linting and formatting** - Ensures code quality with ruff
- **Type checking** - Static analysis with mypy

### Conditional Jobs

#### Integration Tests
Runs when:
- Manual workflow dispatch with `run_integration: true`
- Weekly schedule (Sundays 2 AM UTC)
- Commit message contains `[integration]`

#### Cross-Platform Tests
Runs when:
- Manual workflow dispatch with `run_cross_platform: true`  
- Git tag push (releases)
- Commit message contains `[cross-platform]`

#### Security Scans
Runs when:
- Weekly schedule (Sundays 2 AM UTC)
- Git tag push (releases)
- Commit message contains `[security]`

#### GitHub Release
Runs when:
- Git tag push (e.g., `v1.0.0`)
- Creates a GitHub release with auto-generated notes

## Local Development

### Quick Testing
Use the provided scripts for fast local feedback:

**Windows:**
```powershell
./scripts/quick-test.ps1
./scripts/quick-test.ps1 -Pattern "test_config"
```

**Unix/Linux/macOS:**
```bash
./scripts/quick-test.sh
./scripts/quick-test.sh "test_config"
```

### Manual Workflow Triggers

You can manually trigger the workflow with specific options:

1. Go to GitHub Actions tab
2. Select "CI/CD Pipeline" 
3. Click "Run workflow"
4. Choose options:
   - ✅ Run integration tests
   - ✅ Run cross-platform tests

### Commit Message Tags

Force specific jobs to run by including tags in your commit message:

```bash
git commit -m "feat: new feature [integration]"
git commit -m "fix: cross-platform bug [cross-platform]" 
git commit -m "security: update dependencies [security]"
```

## Performance Benefits

- **Reduced CI time**: ~5 minutes vs previous ~20+ minutes
- **Resource efficiency**: Only runs necessary tests
- **Fast feedback**: Core tests complete quickly
- **Smart scheduling**: Heavy tests run when needed

## Migration from Old Workflows

The following workflows were consolidated:
- `ci.yml` ✅ → Merged into main workflow
- `quick-test.yml` ✅ → Now the default behavior
- `test-coverage.yml` ✅ → Integrated into main job
- `test.yml` ✅ → Cross-platform tests moved to conditional job
- `manual-test.yml` ✅ → Replaced with workflow_dispatch
- `release.yml` ✅ → Integrated as conditional job

This provides the same functionality with better organization and performance.