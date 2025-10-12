# VSCode Integration Tests Troubleshooting

## The Problem
VSCode test runner may use a different Python environment than your terminal, causing Docker SDK import issues.

## Solutions (try in order)

### 1. Check Your VSCode Environment
Run this script to see what's happening in VSCode:
```bash
python3 scripts/check_vscode_environment.py
```

### 2. Set VSCode Python Interpreter
1. Open Command Palette: `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type: "Python: Select Interpreter"
3. Choose the same Python interpreter that works in your terminal:
   ```bash
   which python3
   ```

### 3. Install Docker SDK in VSCode Environment
If VSCode is using a different Python environment:
```bash
# Find VSCode's Python interpreter path from step 2, then:
/path/to/vscode/python -m pip install docker
```

### 4. Use VSCode Terminal
Run tests in VSCode's integrated terminal instead of the test runner:
```bash
python3 -m pytest tests/integration/ -v
```

### 5. Reset VSCode Python Extension
1. Disable Python extension
2. Reload VSCode
3. Re-enable Python extension
4. Set interpreter again

## What We Fixed
- Enhanced Docker client creation with multiple fallback methods
- Added detailed error messages for troubleshooting
- Created VSCode settings file (`.vscode/settings.json`)
- Added environment debugging script

## Current Status
✅ Command line tests: All 6 integration tests passing
✅ Enhanced error handling for different environments
✅ Fallback Docker client creation methods

The enhanced conftest.py should now provide much better error messages if there are still issues in VSCode.
