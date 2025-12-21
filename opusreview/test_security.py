#!/usr/bin/env python3
"""
SLOMIX Bot Security Test Suite
Run this after implementing security fixes to verify they work correctly
"""

import asyncio
import sys
import os
import re
from pathlib import Path
from typing import List, Tuple

# Add bot directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SecurityTester:
    """Automated security testing for SLOMIX bot"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests_run = []

    def print_header(self, title: str):
        """Print test section header"""
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")

    def test_result(self, test_name: str, passed: bool, details: str = ""):
        """Record and print test result"""
        if passed:
            self.passed += 1
            print(f"✅ {test_name}")
        else:
            self.failed += 1
            print(f"❌ {test_name}")

        if details:
            print(f"   {details}")

        self.tests_run.append((test_name, passed))

    def test_ssh_security(self) -> bool:
        """Test SSH host key verification"""
        self.print_header("SSH Security Tests")

        # Check for AutoAddPolicy usage
        vulnerable_files = []
        bot_dir = Path("bot/")

        for py_file in bot_dir.rglob("*.py"):
            content = py_file.read_text()
            if "AutoAddPolicy()" in content:
                # Check if it's commented out or in the new secure module
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if "AutoAddPolicy()" in line and not line.strip().startswith('#'):
                        vulnerable_files.append(f"{py_file}:{i}")

        self.test_result(
            "No AutoAddPolicy() usage",
            len(vulnerable_files) == 0,
            f"Found in: {', '.join(vulnerable_files[:3])}" if vulnerable_files else ""
        )

        # Check for secure SSH module
        secure_ssh_path = Path("bot/core/secure_ssh.py")
        self.test_result(
            "Secure SSH module exists",
            secure_ssh_path.exists()
        )

        return len(vulnerable_files) == 0

    def test_sql_injection_prevention(self) -> bool:
        """Test for SQL injection vulnerabilities"""
        self.print_header("SQL Injection Prevention Tests")

        vulnerable_patterns = [
            (r'f".*SELECT.*\{.*\}"', "f-string in SQL query"),
            (r'f".*INSERT.*\{.*\}"', "f-string in SQL query"),
            (r'f".*UPDATE.*\{.*\}"', "f-string in SQL query"),
            (r'f".*DELETE.*\{.*\}"', "f-string in SQL query"),
            (r'%\s*s(?!afe)', "%-formatting in SQL (use $1, $2 for PostgreSQL)"),
            (r'\.format\(.*SELECT', "format() in SQL query"),
        ]

        issues_found = []
        bot_dir = Path("bot/")

        for py_file in bot_dir.rglob("*.py"):
            if "secure_database.py" in str(py_file):
                continue  # Skip our secure module

            content = py_file.read_text()
            for pattern, description in vulnerable_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    issues_found.append(f"{py_file.name}: {description}")

        self.test_result(
            "No SQL string concatenation",
            len(issues_found) == 0,
            f"Issues: {', '.join(issues_found[:3])}" if issues_found else ""
        )

        # Check for secure database module
        secure_db_path = Path("bot/core/secure_database.py")
        self.test_result(
            "Secure database module exists",
            secure_db_path.exists()
        )

        return len(issues_found) == 0

    def test_command_injection_prevention(self) -> bool:
        """Test for command injection vulnerabilities"""
        self.print_header("Command Injection Prevention Tests")

        # Check for unsafe shell command usage
        unsafe_patterns = [
            (r'os\.system\(', "os.system() usage"),
            (r'subprocess\.call\([^,\]]*\+', "subprocess with concatenation"),
            (r'exec_command\([^)]*\+', "exec_command with concatenation"),
            (r'exec_command\(f["\']', "exec_command with f-string"),
        ]

        issues_found = []
        bot_dir = Path("bot/")

        for py_file in bot_dir.rglob("*.py"):
            content = py_file.read_text()
            for pattern, description in unsafe_patterns:
                if re.search(pattern, content):
                    issues_found.append(f"{py_file.name}: {description}")

        self.test_result(
            "No unsafe command execution",
            len(issues_found) == 0,
            f"Issues: {', '.join(issues_found[:3])}" if issues_found else ""
        )

        # Check for shlex usage
        shlex_usage = []
        for py_file in bot_dir.rglob("*.py"):
            content = py_file.read_text()
            if "import shlex" in content or "from shlex import" in content:
                shlex_usage.append(py_file.name)

        self.test_result(
            "Using shlex for command escaping",
            len(shlex_usage) > 0,
            f"Found in: {', '.join(shlex_usage)}" if shlex_usage else "Not found!"
        )

        return len(issues_found) == 0 and len(shlex_usage) > 0

    def test_secure_config(self) -> bool:
        """Test secure configuration management"""
        self.print_header("Secure Configuration Tests")

        # Check for hardcoded secrets
        secret_patterns = [
            (r'token\s*=\s*["\'][^"\']+["\']', "Hardcoded token"),
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
        ]

        issues_found = []
        bot_dir = Path("bot/")

        for py_file in bot_dir.rglob("*.py"):
            if "test" in str(py_file).lower() or "example" in str(py_file).lower():
                continue

            content = py_file.read_text()
            for pattern, description in secret_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Check if it's not a placeholder
                    if not any(placeholder in match.group() for placeholder in
                              ['""', "''", 'None', 'os.', 'getenv', 'config.', 'self.']):
                        issues_found.append(f"{py_file.name}: {description}")

        self.test_result(
            "No hardcoded secrets",
            len(issues_found) == 0,
            f"Found: {', '.join(issues_found[:3])}" if issues_found else ""
        )

        # Check for secure config module
        secure_config_path = Path("bot/core/secure_config.py")
        self.test_result(
            "Secure config module exists",
            secure_config_path.exists()
        )

        # Check for setup_secrets script
        setup_secrets_path = Path("setup_secrets.py")
        self.test_result(
            "Setup secrets script exists",
            setup_secrets_path.exists()
        )

        return len(issues_found) == 0

    def test_input_validation(self) -> bool:
        """Test input validation implementation"""
        self.print_header("Input Validation Tests")

        # Check for validators module
        validators_path = Path("bot/core/validators.py")
        self.test_result(
            "Validators module exists",
            validators_path.exists()
        )

        # Check for validation usage in cogs
        validation_usage = []
        cogs_dir = Path("bot/cogs/")

        if cogs_dir.exists():
            for py_file in cogs_dir.glob("*.py"):
                content = py_file.read_text()
                if any(term in content for term in
                      ['validate_', 'validator', 'InputValidator', 'sanitize_']):
                    validation_usage.append(py_file.name)

        self.test_result(
            "Input validation in use",
            len(validation_usage) > 0,
            f"Found in: {', '.join(validation_usage)}" if validation_usage else "Not found!"
        )

        return validators_path.exists() and len(validation_usage) > 0

    def test_rate_limiting(self) -> bool:
        """Test rate limiting implementation"""
        self.print_header("Rate Limiting Tests")

        # Check for rate limiter module
        rate_limiter_path = Path("bot/core/rate_limiter.py")
        self.test_result(
            "Rate limiter module exists",
            rate_limiter_path.exists()
        )

        # Check for rate limiting usage
        rate_limit_usage = []
        bot_dir = Path("bot/")

        for py_file in bot_dir.rglob("*.py"):
            content = py_file.read_text()
            if any(term in content for term in
                  ['@rate_limit', '@commands.cooldown', 'RateLimiter']):
                rate_limit_usage.append(py_file.name)

        self.test_result(
            "Rate limiting in use",
            len(rate_limit_usage) > 0,
            f"Found in: {', '.join(rate_limit_usage[:5])}" if rate_limit_usage else "Not found!"
        )

        return rate_limiter_path.exists() or len(rate_limit_usage) > 0

    def test_audit_logging(self) -> bool:
        """Test audit logging implementation"""
        self.print_header("Audit Logging Tests")

        # Check for audit logger module
        audit_logger_path = Path("bot/core/audit_logger.py")
        self.test_result(
            "Audit logger module exists",
            audit_logger_path.exists()
        )

        # Check for audit directory
        audit_dir = Path("logs/audit/")
        self.test_result(
            "Audit log directory exists",
            audit_dir.exists() or Path("logs/").exists()
        )

        # Check for audit logging usage
        audit_usage = []
        bot_dir = Path("bot/")

        for py_file in bot_dir.rglob("*.py"):
            content = py_file.read_text()
            if any(term in content for term in
                  ['audit_log', 'AuditLogger', 'log_action', 'log_command']):
                audit_usage.append(py_file.name)

        self.test_result(
            "Audit logging in use",
            len(audit_usage) > 0,
            f"Found in: {', '.join(audit_usage[:5])}" if audit_usage else "Not found!"
        )

        return audit_logger_path.exists() or len(audit_usage) > 0

    def test_ssl_configuration(self) -> bool:
        """Test SSL/TLS configuration"""
        self.print_header("SSL/TLS Configuration Tests")

        # Check PostgreSQL SSL settings
        ssl_issues = []
        config_files = list(Path(".").glob("*.env*")) + list(Path("bot/").glob("config*.py"))

        for config_file in config_files:
            if config_file.exists():
                content = config_file.read_text()
                if "ssl_mode.*disable" in content.lower() or "sslmode.*disable" in content.lower():
                    ssl_issues.append(f"{config_file.name}: SSL disabled")

        self.test_result(
            "PostgreSQL SSL enabled",
            len(ssl_issues) == 0,
            f"Issues: {', '.join(ssl_issues)}" if ssl_issues else ""
        )

        return len(ssl_issues) == 0

    def run_all_tests(self):
        """Run all security tests"""
        print("\n" + "=" * 60)
        print("  SLOMIX BOT SECURITY TEST SUITE")
        print("=" * 60)

        # Run tests
        self.test_ssh_security()
        self.test_sql_injection_prevention()
        self.test_command_injection_prevention()
        self.test_secure_config()
        self.test_input_validation()
        self.test_rate_limiting()
        self.test_audit_logging()
        self.test_ssl_configuration()

        # Print summary
        print("\n" + "=" * 60)
        print("  TEST SUMMARY")
        print("=" * 60)
        print(f"  ✅ Passed: {self.passed}")
        print(f"  ❌ Failed: {self.failed}")
        print(f"  Total: {self.passed + self.failed}")

        if self.failed == 0:
            print("\n  🎉 ALL SECURITY TESTS PASSED!")
        else:
            print("\n  ⚠️  SECURITY ISSUES DETECTED - FIX BEFORE DEPLOYMENT")

        print("=" * 60 + "\n")

        return self.failed == 0


if __name__ == "__main__":
    tester = SecurityTester()
    success = tester.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
