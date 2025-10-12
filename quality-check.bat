@echo off
REM Quality check batch file for Windows

set "SCRIPT_DIR=%~dp0scripts"

if "%1"=="" (
    echo Running basic quality check...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\quality-check.ps1"
) else if "%1"=="fix" (
    echo Running quality check with auto-fix...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\quality-check.ps1" -Fix
) else if "%1"=="strict" (
    echo Running strict quality check...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\quality-check.ps1" -Strict
) else if "%1"=="all" (
    echo Running all quality checks with fixes...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\quality-check.ps1" -All
) else if "%1"=="type" (
    echo Running type checking...
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\quality-check.ps1" -TypeCheck
) else (
    echo Usage: quality-check.bat [fix^|strict^|all^|type]
    echo.
    echo   fix     - Run with auto-fixes
    echo   strict  - Run strict checks for CI
    echo   all     - Run all checks with fixes
    echo   type    - Run only type checking
    echo   ^(none^)  - Run basic checks
)
