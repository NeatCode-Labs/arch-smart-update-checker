# Contributing to Arch Smart Update Checker

Thank you for your interest in contributing to Arch Smart Update Checker! This project is now licensed under the GNU General Public License version 3.0 or later (GPL-3.0+).

## License Requirements

### Developer Certificate of Origin (DCO)

This project uses the Developer Certificate of Origin (DCO) instead of Contributor License Agreements (CLAs). By contributing to this project, you certify that:

1. You have the right to submit the work contained in your contribution
2. You license your contribution under the GPL-3.0-or-later license
3. You understand and agree that your contribution is public and that a record of it may be maintained indefinitely

### How to Sign Your Commits

Every commit must include a `Signed-off-by` line. You can add this automatically by using the `-s` flag with git commit:

```bash
git commit -s -m "Your commit message"
```

This adds a line that looks like:
```
Signed-off-by: Your Name <your.email@example.com>
```

### GPL-3.0+ License

All contributions must be compatible with the GPL-3.0-or-later license. By contributing, you agree that your contributions will be licensed under the same terms as the project.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/neatcodelabs/arch-smart-update-checker.git
   cd arch-smart-update-checker
   ```

2. **Set up development environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .[dev]
   ```

3. **Run tests:**
   ```bash
   pytest
   ```

4. **Check code style:**
   ```bash
   flake8 src/
   mypy src/
   ```

## Code Standards

### Python Code Style
- Follow PEP 8 style guidelines
- Use Black for code formatting: `black src/`
- Run flake8 for linting: `flake8 src/`
- Use type hints and run mypy: `mypy src/`

### SPDX License Headers
All Python source files must include the SPDX license identifier:
```python
# SPDX-License-Identifier: GPL-3.0-or-later
```

### Security
- Preserve all existing security measures
- Do not compromise input validation, path sanitization, or secure temp file handling
- Follow the principle of least privilege
- Validate all user inputs
- **Review [Security Guidelines](docs/SECURITY_GUIDELINES.md) for detailed requirements**

## Security Guidelines

**Important**: All contributors must follow our security guidelines to maintain the high security standards of this project.

Please review the [Security Guidelines for Contributors](docs/SECURITY_GUIDELINES.md) before making any code changes. Key points:

- Always validate user input using existing validators
- Use `SecureSubprocess` for all external command execution
- Never use `subprocess` directly or with `shell=True`
- Log security events with `log_security_event()`
- Write security tests for any new features
- Report vulnerabilities privately to neatcodelabs@gmail.com

For the complete security checklist and examples, see [docs/SECURITY_GUIDELINES.md](docs/SECURITY_GUIDELINES.md).

## Submitting Changes

1. **Fork the repository** and create a feature branch from `main`
2. **Make your changes** following the code standards above
3. **Add tests** for any new functionality
4. **Ensure all tests pass** and linting checks succeed
5. **Sign your commits** with the DCO using `git commit -s`
6. **Submit a pull request** with a clear description of your changes

### Pull Request Guidelines

- Include a clear description of what your changes do
- Reference any related issues with `Fixes #<issue-number>`
- Ensure your PR has a clear, descriptive title
- All commits must be signed with DCO (`Signed-off-by` line)
- Include tests for new features or bug fixes
- Update documentation if needed

## What We Look For

- **Functionality**: Does the code work as intended?
- **Tests**: Are there appropriate tests covering the changes?
- **Documentation**: Is code well-documented and self-explanatory?
- **Security**: Are security best practices followed?
- **Performance**: Are there any performance implications?
- **Compatibility**: Does it work across supported Python versions?

## Issues and Feature Requests

- Use GitHub Issues to report bugs or request features
- Search existing issues before creating a new one
- Provide clear, detailed descriptions with steps to reproduce for bugs
- For feature requests, explain the use case and expected behavior

## Code of Conduct

- Be respectful and inclusive in all interactions
- Focus on constructive feedback and collaboration
- Welcome newcomers and help them get started
- Maintain a professional and friendly environment

## Questions?

If you have questions about contributing, feel free to:
- Open a GitHub issue with the "question" label
- Start a discussion in GitHub Discussions
- Contact the maintainers at neatcodelabs@gmail.com

## License Migration Note

This project recently migrated from MIT to GPL-3.0+. All past contributors have provided consent for this relicensing. Future contributions must be compatible with GPL-3.0+ and follow the DCO process outlined above.

---

Thank you for helping make Arch Smart Update Checker better! 