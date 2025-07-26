# Security Guidelines for Contributors

## Table of Contents
1. [Introduction](#introduction)
2. [Security Principles](#security-principles)
3. [Secure Coding Practices](#secure-coding-practices)
4. [Input Validation](#input-validation)
5. [Command Execution](#command-execution)
6. [Dependency Management](#dependency-management)
7. [Security Testing](#security-testing)
8. [Incident Response](#incident-response)

## Introduction

This document provides security guidelines for contributors to the Arch Smart Update Checker project. Following these guidelines helps maintain the high security standards of the application and protects our users.

## Security Principles

### 1. Defense in Depth
- Never rely on a single security control
- Implement multiple layers of protection
- Assume any single control might fail

### 2. Least Privilege
- Code should run with minimal necessary permissions
- Never request sudo/root unless absolutely necessary
- Drop privileges as soon as possible

### 3. Fail Securely
- Errors should not expose sensitive information
- Default to denying access when in doubt
- Log security events for monitoring

### 4. Zero Trust
- Never trust user input
- Validate all external data
- Assume the environment might be compromised

## Secure Coding Practices

### Input Validation

**Always validate input using the existing validators:**

```python
from src.utils.validators import validate_package_name, validate_url_enhanced

# Good - using validators
if not validate_package_name(user_input):
    raise ValueError("Invalid package name")

# Bad - no validation
subprocess.run(["pacman", "-S", user_input])  # NEVER DO THIS!
```

### Command Execution

**Use SecureSubprocess for all external commands:**

```python
from src.utils.subprocess_wrapper import SecureSubprocess

# Good - using secure wrapper
SecureSubprocess.run_pacman(["-Syu"], require_sudo=True)

# Bad - direct subprocess
subprocess.run(["sudo", "pacman", "-Syu"])  # NEVER DO THIS!
```

### Path Handling

**Always validate file paths:**

```python
from src.utils.validators import validate_file_path_enhanced

# Good - validated path
if validate_file_path_enhanced(file_path, must_exist=True):
    with open(file_path, 'r') as f:
        content = f.read()

# Bad - unvalidated path
with open(user_provided_path, 'r') as f:  # Path traversal risk!
    content = f.read()
```

### URL Handling

**Use secure URL opening:**

```python
from src.utils.subprocess_wrapper import SecureSubprocess

# Good - sandboxed URL opening
SecureSubprocess.open_url_securely(url, sandbox=True)

# Bad - direct browser opening
import webbrowser
webbrowser.open(url)  # No validation or sandboxing!
```

## Input Validation Requirements

### Package Names
- Must match pattern: `^[a-zA-Z0-9][a-zA-Z0-9\-_.+]*$`
- Maximum length: 100 characters
- No path traversal sequences
- No shell metacharacters

### URLs
- Must be valid HTTP/HTTPS URLs
- HTTPS required for non-localhost
- No JavaScript or data: URLs
- Domain validation against trusted list

### File Paths
- Must be absolute paths under allowed directories
- No path traversal patterns (including encoded)
- No null bytes or control characters
- Must pass normalization checks

### Command Arguments
- Strict whitelisting for commands
- No shell metacharacters
- Length limits enforced
- Encoding validation

## Command Execution Security

### Whitelisted Commands
Only these commands can be executed:
- `pacman` - Package manager
- `checkupdates` - Update checking
- `paccache` - Cache management
- `bwrap` - Sandboxing tool (built-in)
- AppArmor profiles available in `security/apparmor/` for system-wide MAC

### Privileged Commands
These require special handling via secure wrappers:
- `systemctl` - Use `SecureSubprocess.run_systemctl()`
- `mount` - Use `SecureSubprocess.run_mount()`
- `umount` - Use `SecureSubprocess.run_umount()`

### Sandboxing
Always prefer sandboxed execution:
```python
# Enable sandboxing by default
result = SecureSubprocess.run(cmd, sandbox='bwrap')
```

## Dependency Management

### Adding Dependencies
1. Minimize dependencies - each one is a potential attack vector
2. Review security history of the package
3. Pin to specific versions in `pyproject.toml`
4. Run security scan: `pip-audit`

### Security Scanning
Before committing:
```bash
pip-audit --desc
bandit -r src/
mypy src/ --strict
```

## Security Testing

### Unit Tests
Write security-specific tests:
```python
def test_path_traversal_blocked():
    """Ensure path traversal attempts are blocked."""
    assert not validate_file_path_enhanced("../../etc/passwd")
    assert not validate_file_path_enhanced("/home/../etc/passwd")
```

### Integration Tests
Test security controls work together:
```python
def test_secure_command_execution():
    """Test command execution with all security layers."""
    with pytest.raises(ValueError):
        SecureSubprocess.run(["rm", "-rf", "/"])  # Should be blocked
```

### Manual Security Testing
Before major releases:
1. Run static analysis tools
2. Test with malformed inputs
3. Check for information disclosure
4. Verify privilege separation

## Logging Security Events

Always log security-relevant events:
```python
from src.utils.logger import log_security_event

# Log failed validation
log_security_event(
    "INVALID_PACKAGE_NAME",
    {"input": sanitized_input, "source": "user_input"},
    severity="warning"
)

# Log privileged operations
log_security_event(
    "PRIVILEGED_COMMAND",
    {"command": "systemctl", "action": "restart"},
    severity="info"
)
```

## Error Handling

### Safe Error Messages
```python
# Good - generic error
return "Invalid input provided"

# Bad - exposes system details
return f"Failed to open {full_file_path}: {detailed_error}"
```

### Secure Defaults
```python
# Good - default to secure state
def is_allowed(permission):
    return permissions.get(permission, False)  # Default: deny

# Bad - default to insecure state
def is_allowed(permission):
    return permissions.get(permission, True)  # Default: allow
```

## Incident Response

### If You Find a Vulnerability
1. **Do NOT** create a public issue
2. Email security details to: neatcodelabs@gmail.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Security Event Monitoring
Check security metrics regularly:
```python
from src.utils.security_metrics import get_metrics_collector

collector = get_metrics_collector()
report = collector.generate_security_report()
```

## Code Review Checklist

Before approving PRs, check:

- [ ] All user input is validated
- [ ] External commands use SecureSubprocess
- [ ] File paths are validated
- [ ] URLs are validated and sandboxed
- [ ] No hardcoded credentials or secrets
- [ ] Error messages don't leak sensitive info
- [ ] Security events are logged
- [ ] Tests include security scenarios
- [ ] Dependencies are scanned for vulnerabilities

## Additional Resources

- [OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
- [Python Security Guidelines](https://python.readthedocs.io/en/latest/library/security_warnings.html)
- [CWE Top 25](https://cwe.mitre.org/top25/archive/2023/2023_top25_list.html)

## Questions?

For security-related questions:
- Email: neatcodelabs@gmail.com
- Check existing security documentation in `/docs`
- Review security implementation in `/src/utils/`

Remember: **When in doubt, choose the more secure option!** 