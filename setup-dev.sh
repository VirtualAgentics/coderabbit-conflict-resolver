#!/bin/bash
# Development setup script for Review Bot Automator

set -e  # Exit on any error

echo "🚀 Setting up Review Bot Automator development environment..."

# Check if Python 3.12 is available
if ! command -v python3.12 &> /dev/null; then
    echo "❌ Python 3.12 not found. Please install Python 3.12 first."
    echo "   Using pyenv (recommended):"
    echo "   pyenv install 3.12.8"
    echo "   pyenv local 3.12.8"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3.12 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ "$PYTHON_VERSION" != "3.12" ]]; then
    echo "❌ Python 3.12 required, found $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python 3.12 found"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3.12 -m venv .venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip (hash-pinned for security)
echo "⬆️  Upgrading pip..."
pip install --require-hashes -r .github/requirements-bootstrap.txt

# Install dependencies with hash verification
echo "📚 Installing dev dependencies with hash verification..."
pip install --require-hashes -r requirements-dev.txt

echo "📦 Installing project in editable mode..."
pip install --no-deps -e .

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Run initial checks
echo "🧪 Running initial checks..."
echo "  - Linting..."
black --check src/ tests/ || echo "⚠️  Black formatting issues found (run 'make format' to fix)"
ruff check src/ tests/ || echo "⚠️  Ruff linting issues found (run 'make format' to fix)"

echo "  - Type checking..."
mypy src/ || echo "⚠️  MyPy type checking issues found"

echo "  - Running tests..."
pytest tests/ --cov=src --cov-report=term-missing || echo "⚠️  Some tests failed"

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Activate the virtual environment: source .venv/bin/activate"
echo "  2. Run all checks: make check-all"
echo "  3. Start coding! 🚀"
echo ""
echo "Useful commands:"
echo "  make help          - Show all available commands"
echo "  make test          - Run tests"
echo "  make lint          - Run linters"
echo "  make format        - Auto-format code"
echo "  make docs          - Build documentation"
echo "  make clean         - Clean build artifacts"
