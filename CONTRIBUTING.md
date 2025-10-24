# Contributing to CodeRabbit Conflict Resolver

Thank you for your interest in contributing to CodeRabbit Conflict Resolver! This document provides guidelines and information for contributors.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Development Setup

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/coderabbit-conflict-resolver.git
   cd coderabbit-conflict-resolver
   ```

3. **Set up development environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   pre-commit install
   ```

4. **Run tests** to ensure everything works:
   ```bash
   pytest tests/ --cov=src --cov-report=html
   ```

### Development Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the coding standards below

3. **Run tests and linting**:
   ```bash
   pytest tests/
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   ```

4. **Commit your changes** with a clear commit message

5. **Push to your fork** and create a pull request

## Coding Standards

### Python Code Style

- **Formatting**: Use [Black](https://black.readthedocs.io/) with line length 100
- **Linting**: Use [Ruff](https://docs.astral.sh/ruff/) for fast linting
- **Type hints**: Use [MyPy](https://mypy.readthedocs.io/) for type checking
- **Imports**: Sort imports with `ruff` (handled automatically)

### Code Organization

- **Modules**: Keep related functionality together
- **Classes**: Use clear, descriptive names
- **Functions**: Keep functions small and focused
- **Documentation**: Add docstrings for all public functions and classes

### Testing

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test component interactions
- **Coverage**: Maintain >80% test coverage
- **Fixtures**: Use pytest fixtures for test data

### Documentation

- **Docstrings**: Use Google-style docstrings
- **Type hints**: Include type hints for all function parameters and returns
- **Examples**: Include usage examples in docstrings
- **README**: Keep README.md updated with new features

## Pull Request Process

### Before Submitting

1. **Run all tests**: `pytest tests/`
2. **Check code quality**: `black --check src/ tests/` and `ruff check src/ tests/`
3. **Type checking**: `mypy src/`
4. **Update documentation** if needed
5. **Add tests** for new functionality

### Pull Request Template

When creating a pull request, please include:

- **Description**: What changes were made and why
- **Type**: Bug fix, feature, documentation, refactoring, etc.
- **Testing**: How the changes were tested
- **Breaking changes**: Any breaking changes and migration steps
- **Related issues**: Link to related issues

### Review Process

1. **Automated checks** must pass (CI/CD pipeline)
2. **Code review** by maintainers
3. **Testing** on multiple environments
4. **Documentation** review
5. **Approval** from at least one maintainer

## Types of Contributions

### Bug Reports

When reporting bugs, please include:

- **Description**: Clear description of the bug
- **Steps to reproduce**: Detailed steps to reproduce the issue
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Environment**: OS, Python version, package version
- **Screenshots**: If applicable

### Feature Requests

When requesting features, please include:

- **Use case**: Why this feature would be useful
- **Proposed solution**: How you think it should work
- **Alternatives**: Other solutions you've considered
- **Additional context**: Any other relevant information

### Code Contributions

We welcome contributions in these areas:

- **Bug fixes**: Fixing existing issues
- **New features**: Adding new functionality
- **Performance**: Optimizing existing code
- **Documentation**: Improving documentation
- **Tests**: Adding or improving tests
- **Refactoring**: Improving code structure

## Development Areas

### Core Components

- **Conflict Detection**: `src/pr_conflict_resolver/analysis/`
- **Resolution Strategies**: `src/pr_conflict_resolver/strategies/`
- **File Handlers**: `src/pr_conflict_resolver/handlers/`
- **GitHub Integration**: `src/pr_conflict_resolver/integrations/`

### Testing

- **Unit Tests**: `tests/unit/`
- **Integration Tests**: `tests/integration/`
- **Fixtures**: `tests/fixtures/`

### Documentation

- **API Reference**: `docs/api-reference.md`
- **Architecture**: `docs/architecture.md`
- **Configuration**: `docs/configuration.md`
- **Examples**: `examples/`

## Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality in a backwards compatible manner
- **PATCH**: Backwards compatible bug fixes

### Release Steps

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with new features and fixes
3. **Create release tag**: `git tag v1.0.0`
4. **Push tag**: `git push origin v1.0.0`
5. **GitHub Actions** will automatically build and publish to PyPI

## Getting Help

### Questions and Support

- **GitHub Issues**: For bug reports and feature requests
- **Discussions**: For questions and general discussion
- **Documentation**: Check the docs/ directory for detailed information

### Community

- **Code of Conduct**: Please read and follow our code of conduct
- **Respect**: Be respectful and constructive in all interactions
- **Learning**: Help others learn and grow
- **Collaboration**: Work together to improve the project

## Recognition

Contributors will be recognized in:

- **CONTRIBUTORS.md**: List of all contributors
- **Release notes**: Mentioned in release announcements
- **GitHub**: Listed as contributors on the repository

Thank you for contributing to CodeRabbit Conflict Resolver! 🎉
