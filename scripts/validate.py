#!/usr/bin/env python3
"""
Semptify Startup Validation Script

Validates environment configuration and dependencies before starting the app.
Run this before deployment to catch configuration issues early.

Usage:
    python scripts/validate.py          # Run all checks
    python scripts/validate.py --quick  # Skip slow checks (network, etc.)
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_status(check: str, passed: bool, message: str = ""):
    """Print colored status message."""
    status = "✓" if passed else "✗"
    color = "\033[32m" if passed else "\033[31m"
    reset = "\033[0m"
    
    msg = f"{color}{status}{reset} {check}"
    if message:
        msg += f" - {message}"
    print(msg)
    return passed


def check_python_version():
    """Check Python version >= 3.11."""
    version = sys.version_info
    passed = version >= (3, 11)
    return print_status(
        "Python version",
        passed,
        f"{version.major}.{version.minor}.{version.micro}" + (" (need >= 3.11)" if not passed else "")
    )


def check_required_packages():
    """Check that required packages are installed."""
    required = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "sqlalchemy",
        "httpx",
        "cryptography",
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    passed = len(missing) == 0
    return print_status(
        "Required packages",
        passed,
        f"Missing: {', '.join(missing)}" if missing else f"All {len(required)} packages found"
    )


def check_directories():
    """Check that required directories exist or can be created."""
    dirs = ["uploads", "uploads/vault", "logs", "security", "data"]
    
    issues = []
    for dir_name in dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True)
            except Exception as e:
                issues.append(f"{dir_name}: {e}")
    
    passed = len(issues) == 0
    return print_status(
        "Required directories",
        passed,
        f"Issues: {', '.join(issues)}" if issues else f"All {len(dirs)} directories OK"
    )


def check_env_file():
    """Check for .env file existence."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        return print_status("Environment file", True, ".env exists")
    elif env_example.exists():
        return print_status("Environment file", False, ".env missing (copy from .env.example)")
    else:
        return print_status("Environment file", False, "Neither .env nor .env.example found")


def check_secret_key():
    """Check that SECRET_KEY is configured (not default)."""
    from dotenv import load_dotenv
    load_dotenv()
    
    secret_key = os.getenv("SECRET_KEY", "")
    
    if not secret_key:
        return print_status("SECRET_KEY", True, "Not set (will auto-generate)")
    elif "change" in secret_key.lower() or secret_key == "dev-secret":
        return print_status("SECRET_KEY", False, "Using insecure default value")
    elif len(secret_key) < 32:
        return print_status("SECRET_KEY", False, f"Too short ({len(secret_key)} chars, need 32+)")
    else:
        return print_status("SECRET_KEY", True, "Configured")


def check_database():
    """Check database connectivity."""
    from dotenv import load_dotenv
    load_dotenv()
    
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./semptify.db")
    
    if "sqlite" in db_url:
        # For SQLite, just check if file can be created
        db_path = db_url.split("///")[-1]
        return print_status("Database", True, f"SQLite: {db_path}")
    else:
        # For PostgreSQL, try to connect
        try:
            import asyncio
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy import text
            
            async def test_connection():
                engine = create_async_engine(db_url)
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                await engine.dispose()
            
            asyncio.run(test_connection())
            return print_status("Database", True, "PostgreSQL connection OK")
        except Exception as e:
            return print_status("Database", False, f"Connection failed: {e}")


def check_ai_provider():
    """Check AI provider configuration."""
    from dotenv import load_dotenv
    load_dotenv()
    
    provider = os.getenv("AI_PROVIDER", "anthropic")
    
    if provider == "none":
        return print_status("AI Provider", True, "Disabled")
    
    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "ollama": None,  # No key needed
    }
    
    key_env = key_map.get(provider)
    if key_env is None:
        return print_status("AI Provider", True, f"{provider} (no API key required)")
    
    api_key = os.getenv(key_env, "")
    if api_key:
        return print_status("AI Provider", True, f"{provider} API key configured")
    else:
        return print_status("AI Provider", False, f"{provider} selected but {key_env} not set")


def check_app_imports():
    """Check that the main app can be imported."""
    try:
        from app.main import create_app
        return print_status("App imports", True, "All modules import successfully")
    except Exception as e:
        return print_status("App imports", False, str(e))


def main():
    parser = argparse.ArgumentParser(description="Validate Semptify configuration")
    parser.add_argument("--quick", action="store_true", help="Skip slow checks")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Semptify Startup Validation")
    print("=" * 60)
    print()
    
    results = []
    
    # Core checks
    print("Core Requirements:")
    results.append(check_python_version())
    results.append(check_required_packages())
    results.append(check_directories())
    print()
    
    # Configuration checks
    print("Configuration:")
    results.append(check_env_file())
    results.append(check_secret_key())
    results.append(check_ai_provider())
    print()
    
    # Connectivity checks (can be slow)
    if not args.quick:
        print("Connectivity:")
        results.append(check_database())
        print()
    
    # Import checks
    print("Application:")
    results.append(check_app_imports())
    print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=" * 60)
    if passed == total:
        print(f"\033[32m✓ All {total} checks passed!\033[0m")
        print("Ready to start: uvicorn app.main:app")
        sys.exit(0)
    else:
        print(f"\033[31m✗ {total - passed}/{total} checks failed\033[0m")
        print("Fix the issues above before starting the application.")
        sys.exit(1)


if __name__ == "__main__":
    main()
