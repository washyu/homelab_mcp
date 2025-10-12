#!/usr/bin/env python3
"""
Check VSCode Python environment for Docker SDK issues.
Run this script to see what's happening in your environment.
"""

import os
import sys


def main():
    print("🔍 VSCode Environment Debug Information")
    print("=" * 50)

    # Python interpreter info
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    print(f"Python path: {sys.path[:3]}...")  # First 3 entries

    # Current working directory
    print(f"Current working directory: {os.getcwd()}")

    # Try to import docker and see what we get
    print("\n🐳 Docker Module Analysis")
    print("-" * 30)

    try:
        import docker

        print("✅ Docker module imported successfully")
        print(f"   File: {getattr(docker, '__file__', 'Unknown')}")
        print(f"   Version: {getattr(docker, '__version__', 'Unknown')}")
        print(f"   Has from_env: {hasattr(docker, 'from_env')}")
        print(f"   Has DockerClient: {hasattr(docker, 'DockerClient')}")

        # Show first 10 attributes
        attrs = [attr for attr in dir(docker) if not attr.startswith("_")][:10]
        print(f"   First 10 attributes: {attrs}")

        # Try to create client
        if hasattr(docker, "from_env"):
            try:
                client = docker.from_env()
                print("✅ Docker client created successfully")
                client.ping()
                print("✅ Docker daemon is reachable")
            except Exception as e:
                print(f"❌ Docker client creation failed: {e}")
        else:
            print("❌ docker.from_env() not available")

    except ImportError as e:
        print(f"❌ Failed to import docker: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    # Check for conflicting packages
    print("\n📦 Package Information")
    print("-" * 20)

    import subprocess

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list"], capture_output=True, text=True
        )
        docker_packages = [
            line for line in result.stdout.split("\n") if "docker" in line.lower()
        ]
        if docker_packages:
            print("Docker-related packages:")
            for pkg in docker_packages:
                print(f"   {pkg}")
        else:
            print("No docker packages found")
    except Exception as e:
        print(f"Failed to check packages: {e}")

    print("\n🛠️ Recommendations")
    print("-" * 15)
    print("If you see issues:")
    print("1. Make sure VSCode is using the correct Python interpreter")
    print("2. In VSCode: Cmd+Shift+P > 'Python: Select Interpreter'")
    print("3. Choose the same Python that works in terminal")
    print("4. Or install Docker SDK in VSCode's Python environment:")
    print(f"   {sys.executable} -m pip install docker")


if __name__ == "__main__":
    main()
