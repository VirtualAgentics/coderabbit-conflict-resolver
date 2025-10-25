# CodeRabbit Conflict Resolver

An intelligent, automated conflict resolution system for GitHub PR comments, specifically designed for [CodeRabbit AI](https://coderabbit.ai) but extensible to other code review bots.

[![CI](https://github.com/VirtualAgentics/coderabbit-conflict-resolver/workflows/CI/badge.svg)](https://github.com/VirtualAgentics/coderabbit-conflict-resolver/actions)
[![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/VirtualAgentics/coderabbit-conflict-resolver?utm_source=oss&utm_medium=github&utm_campaign=VirtualAgentics%2Fcoderabbit-conflict-resolver&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)](https://coderabbit.ai)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🎯 Problem Statement

When multiple PR review comments suggest overlapping changes to the same file, traditional automation tools either:

- Skip all conflicting changes (losing valuable suggestions)
- Apply changes sequentially without conflict awareness (potentially breaking code)
- Require tedious manual resolution for every conflict

**CodeRabbit Conflict Resolver** provides intelligent, semantic-aware conflict resolution that:

- ✅ Understands code structure (JSON, YAML, TOML, Python, TypeScript)
- ✅ Uses priority-based resolution (user selections, security fixes, syntax errors)
- ✅ Supports semantic merging (combining non-conflicting changes automatically)
- ✅ Learns from your decisions to improve over time
- ✅ Provides detailed conflict analysis and actionable suggestions

## 🚀 Quick Start

### Installation

```bash
pip install pr-conflict-resolver
```

### Basic Usage

```bash
# Analyze conflicts in a PR
pr-resolve analyze --pr 123

# Apply suggestions with conflict resolution
pr-resolve apply --pr 123 --strategy priority

# Simulate without applying changes
pr-resolve simulate --pr 123 --config balanced
```

### Python API

```python
from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.config import PresetConfig

resolver = ConflictResolver(config=PresetConfig.BALANCED)
results = resolver.resolve_pr_conflicts(
    owner="VirtualAgentics",
    repo="my-repo",
    pr_number=123
)

print(f"Applied: {results.applied_count}")
print(f"Conflicts: {results.conflict_count}")
print(f"Success rate: {results.success_rate}%")
```

## 🎨 Features

### Intelligent Conflict Analysis

- **Semantic Understanding**: Analyzes JSON, YAML, TOML structure, not just text
- **Conflict Categorization**: Exact, major, partial, minor, disjoint-keys, semantic-duplicate
- **Impact Assessment**: Evaluates scope, risk level, and criticality of changes
- **Actionable Suggestions**: Provides specific guidance for each conflict

### Smart Resolution Strategies

- **Priority-Based**: User selections > Security fixes > Syntax errors > Regular suggestions
- **Semantic Merging**: Combines non-conflicting changes in structured files
- **Sequential Application**: Applies compatible changes in optimal order
- **Defer to User**: Escalates complex conflicts for manual review

### File-Type Handlers

- **JSON**: Duplicate key detection, key-level merging
- **YAML**: Comment preservation, structure-aware merging
- **TOML**: Section merging, format preservation
- **Python/TypeScript**: AST-aware analysis (planned)

### Learning & Optimization

- **ML-Assisted Priority**: Learns from your resolution decisions
- **Metrics Tracking**: Monitors success rates, resolution times, strategy effectiveness
- **Conflict Caching**: Reuses analysis for similar conflicts
- **Performance**: Parallel processing for large PRs

### Configuration & Presets

- **Conservative**: Skip all conflicts, manual review required
- **Balanced**: Priority system + semantic merging (default)
- **Aggressive**: Maximize automation, user selections always win
- **Semantic**: Focus on structure-aware merging for config files

## 📖 Documentation

- [Getting Started Guide](docs/getting-started.md)
- [Architecture Overview](docs/architecture.md)
- [Configuration Reference](docs/configuration.md)
- [Conflict Types Explained](docs/conflict-types.md)
- [Resolution Strategies](docs/resolution-strategies.md)
- [API Reference](docs/api-reference.md)
- [Contributing Guide](CONTRIBUTING.md)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub PR Comments                       │
│                   (CodeRabbit, Review Bot)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Comment Parser & Extractor                     │
│   (Suggestions, Diffs, Codemods, Multi-Options)            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Conflict Detection Engine                      │
│  • Fingerprinting  • Overlap Analysis  • Semantic Check    │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴──────────┐
         ▼                      ▼
┌──────────────────┐   ┌──────────────────┐
│  File Handlers   │   │  Priority System │
│  • JSON          │   │  • User Selected │
│  • YAML          │   │  • Security Fix  │
│  • TOML          │   │  • Syntax Error  │
│  • Python        │   │  • Regular       │
└─────────┬────────┘   └────────┬─────────┘
          │                     │
          └──────────┬──────────┘
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Resolution Strategy Selector                      │
│  • Skip  • Override  • Merge  • Sequential  • Defer        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Application Engine                             │
│  • Backup  • Apply  • Validate  • Rollback                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│        Reporting & Metrics                                  │
│  • Conflict Summary  • Visual Diff  • Success Rate         │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Use Cases

### 1. CodeRabbit Multi-Option Selections

**Problem**: User selects "Option 2" but it conflicts with another suggestion
**Solution**: Priority system ensures user selections override lower-priority changes

### 2. Overlapping Configuration Changes

**Problem**: Two suggestions modify different keys in `package.json`
**Solution**: Semantic merging combines both changes automatically

### 3. Security Fix vs. Formatting

**Problem**: Security fix conflicts with formatting suggestion
**Solution**: Priority system applies security fix, skips formatting

### 4. Large PR with 50+ Comments

**Problem**: Manual conflict resolution is time-consuming
**Solution**: Parallel processing + caching resolves conflicts in seconds

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/VirtualAgentics/coderabbit-conflict-resolver.git
cd coderabbit-conflict-resolver
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

### Running Tests

```bash
pytest tests/ --cov=src --cov-report=html
```

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Inspired by the sophisticated code review capabilities of [CodeRabbit AI](https://coderabbit.ai)
- Built with experience from [ContextForge Memory](https://github.com/VirtualAgentics/ConextForge_memory) project
- Community feedback and contributions

## 📊 Project Status

**Current Version**: 0.1.0 (Alpha)

**Roadmap**:

- ✅ Phase 0: Repository setup and architecture
- 🔄 Phase 1: Core conflict detection and analysis
- 📅 Phase 2: Priority system and basic strategies
- 📅 Phase 3: Advanced strategies and configuration
- 📅 Phase 4: ML-assisted learning
- 📅 Phase 5: Performance optimization

## 🔗 Related Projects

- [ContextForge Memory](https://github.com/VirtualAgentics/ConextForge_memory) - Original implementation
- [CodeRabbit AI](https://coderabbit.ai) - AI-powered code review

---

**Made with ❤️ by [VirtualAgentics](https://github.com/VirtualAgentics)**
