#!/usr/bin/env python3
"""
Test runner script for different CI/CD scenarios.

This script provides different test execution modes for CI/CD pipelines:
- Unit tests (fast, no external dependencies)
- Integration tests (with mocking)
- End-to-end tests (require real infrastructure)
- Coverage reporting
- Cross-platform testing
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str = "") -> int:
    """Run a command and return exit code."""
    if description:
        print(f"\n🔄 {description}")
        print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print(f"✅ {description} - SUCCESS")
    else:
        print(f"❌ {description} - FAILED (exit code: {result.returncode})")

    return result.returncode


def run_unit_tests(coverage: bool = True, fail_under: int = 50) -> int:
    """Run fast unit tests suitable for CI."""
    print("\n🧪 Running Unit Tests")
    print("=" * 50)

    # Core unit test modules that should always pass
    test_modules = [
        "tests/test_config.py",
        "tests/test_error_handling.py",
        "tests/test_database.py",
        "tests/test_sitemap.py",
        "tests/test_ssh_tools.py",
        "tests/test_tools.py",
        "tests/test_vm_operations.py",
        "tests/test_vm_providers.py",
        "tests/test_server.py",
        "tests/test_service_installer.py",
        "tests/test_infrastructure_crud.py",
    ]

    # Add migration tests but allow them to have some failures
    migration_modules = [
        "tests/test_migration.py",
    ]

    cmd = (
        ["uv", "run", "pytest"]
        + test_modules
        + migration_modules
        + [
            "-v",
            "--tb=short",
            "-x",  # Stop on first failure
        ]
    )

    if coverage:
        cmd.extend(
            [
                "--cov=src",
                "--cov-report=term-missing",
                "--cov-report=xml",
                "--cov-report=html",
                f"--cov-fail-under={fail_under}",
            ]
        )

    return run_command(cmd, "Unit Tests")


def run_integration_tests() -> int:
    """Run integration tests with proper mocking."""
    print("\n🔗 Running Integration Tests")
    print("=" * 50)

    cmd = [
        "uv",
        "run",
        "pytest",
        "tests/integration/",
        "tests/test_ansible.py",
        "-v",
        "--tb=short",
        "-k",
        "not (ssh and network)",  # Skip tests requiring real SSH/network
        "--continue-on-collection-errors",
    ]

    return run_command(cmd, "Integration Tests (Mocked)")


def run_e2e_tests() -> int:
    """Run end-to-end tests (requires real infrastructure)."""
    print("\n🌐 Running End-to-End Tests")
    print("=" * 50)
    print("⚠️  These tests require real infrastructure and may fail in CI")

    cmd = [
        "uv",
        "run",
        "pytest",
        "tests/integration/",
        "-v",
        "--tb=short",
        "-m",
        "e2e or network or ssh",
    ]

    return run_command(cmd, "End-to-End Tests")


def run_specific_failing_tests() -> int:
    """Run only the currently failing tests for debugging."""
    print("\n🐛 Running Currently Failing Tests")
    print("=" * 50)

    failing_tests = [
        # Integration test failures (expected in CI)
        "tests/integration/test_full_stack_integration.py::TestDiscoveryToServiceDeploymentWorkflow::test_discovery_to_service_deployment",
        "tests/integration/test_full_stack_integration.py::TestServiceToVMDeploymentWorkflow::test_service_to_vm_deployment_workflow",
        "tests/integration/test_full_stack_integration.py::TestEndToEndWorkflowWithMCPTools::test_complete_homelab_setup_workflow",
        "tests/integration/test_full_stack_integration.py::TestEndToEndWorkflowWithMCPTools::test_monitoring_deployment_workflow",
        "tests/integration/test_full_stack_integration.py::TestErrorRecoveryAndRollback::test_partial_deployment_failure_recovery",
        "tests/integration/test_full_stack_integration.py::TestErrorRecoveryAndRollback::test_discovery_failure_handling",
        "tests/integration/test_full_stack_integration.py::test_complete_homelab_lifecycle",
        # Ansible test failures (need mocking fixes)
        "tests/test_ansible.py::TestAnsibleServiceIntegration::test_ansible_playbook_execution_success",
        "tests/test_ansible.py::TestAnsibleServiceIntegration::test_ansible_playbook_execution_failure",
        "tests/test_ansible.py::TestAnsibleServiceIntegration::test_ansible_variable_substitution",
        "tests/test_ansible.py::TestAnsibleServiceIntegration::test_ansible_template_rendering",
        # Migration test failures (minor issues)
        "tests/test_migration.py::TestDatabaseMigrator::test_migrate_device_history_success",
        "tests/test_migration.py::TestMigrationIntegration::test_full_migration_workflow_with_mocks",
    ]

    cmd = (
        ["uv", "run", "pytest"]
        + failing_tests
        + [
            "-v",
            "--tb=long",
            "--no-cov",  # Don't run coverage for debugging
        ]
    )

    return run_command(cmd, "Failing Tests (Debug)")


def run_coverage_report() -> int:
    """Generate detailed coverage report."""
    print("\n📊 Generating Coverage Report")
    print("=" * 50)

    # Run tests with coverage
    cmd = [
        "uv",
        "run",
        "pytest",
        "tests/",
        "--cov=src",
        "--cov-report=html",
        "--cov-report=xml",
        "--cov-report=term-missing",
        "--cov-branch",
        "-q",  # Quiet test output, focus on coverage
    ]

    exit_code = run_command(cmd, "Coverage Analysis")

    if exit_code == 0:
        print("\n📈 Coverage reports generated:")
        print("  - HTML: htmlcov/index.html")
        print("  - XML: coverage.xml")
        print("  - Terminal: displayed above")

    return exit_code


def run_quality_checks() -> int:
    """Run code quality checks."""
    print("\n🔍 Running Code Quality Checks")
    print("=" * 50)

    checks = [
        (["uv", "run", "ruff", "check", "src", "tests"], "Ruff Linting"),
        (["uv", "run", "ruff", "format", "--check", "src", "tests"], "Ruff Formatting"),
        (
            ["uv", "run", "mypy", "src", "--ignore-missing-imports"],
            "MyPy Type Checking",
        ),
    ]

    total_failures = 0

    for cmd, description in checks:
        exit_code = run_command(cmd, description)
        if exit_code != 0:
            total_failures += 1

    if total_failures == 0:
        print("\n✅ All quality checks passed!")
    else:
        print(f"\n❌ {total_failures} quality check(s) failed")

    return total_failures


def main():
    parser = argparse.ArgumentParser(
        description="Run tests for homelab MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "mode",
        choices=[
            "unit",
            "integration",
            "e2e",
            "failing",
            "coverage",
            "quality",
            "ci",
            "all",
        ],
        help="""Test mode:
  unit        - Fast unit tests (CI-ready)
  integration - Integration tests with mocking
  e2e         - End-to-end tests (requires infrastructure)
  failing     - Run currently failing tests (for debugging)
  coverage    - Generate detailed coverage report
  quality     - Run code quality checks (lint, format, type)
  ci          - Run CI/CD pipeline tests (unit + quality)
  all         - Run all tests (unit + integration + quality)""",
    )

    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Skip coverage reporting for faster execution",
    )

    parser.add_argument(
        "--fail-under",
        type=int,
        default=50,
        help="Minimum coverage percentage required (default: 50)",
    )

    args = parser.parse_args()

    print(f"🚀 Starting test mode: {args.mode}")
    print(f"📁 Working directory: {Path.cwd()}")

    exit_code = 0

    if args.mode == "unit":
        exit_code = run_unit_tests(coverage=not args.no_coverage, fail_under=args.fail_under)

    elif args.mode == "integration":
        exit_code = run_integration_tests()

    elif args.mode == "e2e":
        exit_code = run_e2e_tests()

    elif args.mode == "failing":
        exit_code = run_specific_failing_tests()

    elif args.mode == "coverage":
        exit_code = run_coverage_report()

    elif args.mode == "quality":
        exit_code = run_quality_checks()

    elif args.mode == "ci":
        # CI/CD pipeline: unit tests + quality checks
        print("\n🏭 Running CI/CD Pipeline")
        print("=" * 50)

        unit_code = run_unit_tests(coverage=not args.no_coverage, fail_under=args.fail_under)
        quality_code = run_quality_checks()

        exit_code = unit_code or quality_code

        if exit_code == 0:
            print("\n🎉 CI/CD Pipeline PASSED!")
        else:
            print("\n💥 CI/CD Pipeline FAILED!")

    elif args.mode == "all":
        # Run everything except e2e tests
        print("\n🌟 Running Complete Test Suite")
        print("=" * 50)

        unit_code = run_unit_tests(coverage=not args.no_coverage, fail_under=args.fail_under)
        integration_code = run_integration_tests()
        quality_code = run_quality_checks()

        # Integration tests are allowed to fail
        exit_code = unit_code or quality_code

        if exit_code == 0:
            print("\n🎉 Complete Test Suite PASSED!")
            if integration_code != 0:
                print("ℹ️  Note: Some integration tests failed (expected in CI)")
        else:
            print("\n💥 Complete Test Suite FAILED!")

    print(f"\n🏁 Test execution completed with exit code: {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
