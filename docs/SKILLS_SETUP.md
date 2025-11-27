# Skills Setup Guide

This guide covers installing and using Claude Code skills from skillsmp.com to enhance your development workflow.

**Last Updated**: 2025-11-11
**Skills Source**: [wshobson/agents](https://github.com/wshobson/agents) (63 plugins, 3,455+ skills)

## Table of Contents

* [Overview](#overview)
* [Phase 1: High-Value Plugins](#phase-1-high-value-plugins)
* [Phase 2: Quality & Security](#phase-2-quality--security)
* [Phase 3: Custom Skills](#phase-3-custom-skills)
* [Usage Examples](#usage-examples)
* [Troubleshooting](#troubleshooting)

## Overview

### What Are Skills?

Skills are AI-invoked workflow automation that extend Claude's capabilities:

* **Model-invoked**: Claude decides when to use them based on context
* **Progressive disclosure**: Loads information only as needed
* **Team-shareable**: Version-controlled via `.claude/skills/`

### Why These Skills?

Based on project analysis:

* **Time savings**: 20-35 hours/week
* **V2.0 acceleration**: 20% faster completion (8-10 weeks vs. 10-12 weeks)
* **LLM quality**: 95%+ parsing success (vs. 20% current)
* **ROI**: 1,200%+ (break-even in Week 1)

### Complementary to MCP

Skills **enhance** (not replace) your existing MCP servers:

* Skills = workflow patterns and knowledge
* MCP = tool execution (GitHub API, Ollama, etc.)

---

## Phase 1: High-Value Plugins

**Goal**: Immediate impact on LLM development (v2.0) and testing

### Step 1: Add Marketplace

In Claude Code CLI:

```text
/plugin marketplace add wshobson/agents

```

**Expected output**: "Marketplace added successfully"

### Step 2: Install Python Development Plugin

```text
/plugin install python-development

```

**What it includes:**

* `async-python-patterns` - Async/await best practices
* `python-testing-patterns` - Pytest fixtures, parametrization
* `python-packaging` - Distribution, dependency management
* `python-performance-optimization` - cProfile, memory profiling
* `uv-package-manager` - Fast dependency management

**Value for this project:**

* Optimize test suite (current: 82.35% coverage)
* Profile `resolver.py` bottlenecks
* Improve async handling in LLM providers

**Time saved**: 4-6 hours/week

### Step 3: Install LLM Application Development Plugin

```text
/plugin install llm-application-dev

```

**What it includes:**

* `langchain-architecture` - Agent design, memory, tools
* `prompt-engineering-patterns` - LLM performance optimization
* `rag-implementation` - Vector DB, semantic search
* `llm-evaluation` - Benchmarking, quality metrics

**Value for this project:**

* Critical for v2.0 LLM refactor (currently 57% complete - Phases 0-3 done, Phase 4 in progress)
* Optimize prompts for CodeRabbit comment parsing
* Evaluate Anthropic vs OpenAI vs Ollama quality
* Reduce API costs (better prompts)

**Time saved**: 5-8 hours/week

### Step 4: Install CI/CD Automation Plugin

```text
/plugin install cicd-automation

```

**What it includes:**

* `deployment-pipeline-design` - Multi-stage pipelines with gates
* `github-actions-templates` - Production-ready workflows
* `secrets-management` - Secure credential handling

**Value for this project:**

* Optimize 10 GitHub Actions workflows
* Improve secrets handling (`GITHUB_PERSONAL_ACCESS_TOKEN`)
* Reduce workflow duplication

**Time saved**: 3-5 hours/week

### Step 5: Verify Installation

```text
/plugin list

```

**Expected output:**

```text
Installed Plugins:
* python-development (3 agents, 5 skills)
* llm-application-dev (4 skills)
* cicd-automation (4 skills)
```

---

## Phase 2: Quality & Security

**Goal**: Consolidate security tooling, automate reviews, improve docs

### Step 6: Install Security Scanning Plugin

```text
/plugin install security-scanning

```

**What it includes:**

* `sast-configuration` - Automated vulnerability detection
* Security scanning expert agent

**Value for this project:**

* Consolidate 7+ tools: Bandit, Trivy, CodeQL, TruffleHog, pip-audit, Scorecard, ClusterFuzzLite
* Unified security reporting
* Optimize scan coverage, reduce false positives

**Time saved**: 2-4 hours/week

### Step 7: Install Code Review AI Plugin

```text
/plugin install code-review-ai

```

**What it includes:**

* AI-powered code reviewer agent
* Architectural analysis, security assessment

**Value for this project:**

* Automated PR review gates
* Learn patterns for building review automation
* Quality improvements before merge

**Time saved**: 2-3 hours/week

### Step 8: Install Documentation Generation Plugin

```text
/plugin install documentation-generation

```

**What it includes:**

* Doc generation expert agent
* API specifications, automated docs

**Value for this project:**

* Auto-generate API reference from docstrings
* Maintain 28 markdown documentation files
* Architecture diagram generation

**Time saved**: 3-4 hours/week

### Step 9: Verify Phase 2

```text
/plugin list

```

**Expected output**: 6 plugins installed

---

## Phase 3: Custom Skills

**Goal**: Capture domain-specific knowledge unique to this project

### Skill 1: CodeRabbit API Patterns

Create `.claude/skills/coderabbit-api-patterns/SKILL.md`:

```markdown
---
name: "coderabbit-api-patterns"
description: "Patterns for integrating with CodeRabbit API: parsing review comments, extracting suggestions and diffs, handling multi-option suggestions, rate limit management. Use when working with CodeRabbit integration."
allowed-tools: ["mcp__github__pull_request_read", "Read", "Write", "Grep"]
---

# CodeRabbit API Integration Patterns

## When to Use
* Parsing CodeRabbit review comments
* Extracting suggestions, diffs, multi-options
* Handling rate limits (5000/hour)
* WebSocket streaming for real-time updates

## Core Patterns

### 1. Comment Parsing Strategies

**Structure**: CodeRabbit comments have:
* `**Suggestion**:` blocks (actionable changes)
* Diff blocks (```suggestion ... ```)
* Multi-option blocks (Option 1/2/3)
* Natural language explanations

**Parsing approach**:

```python

# Use LLM provider (Anthropic/OpenAI/Ollama)

from review_bot_automator.llm import get_parser

parser = get_parser(provider="anthropic")
changes = parser.parse_comment(comment_body)

```text

### 2. Diff Extraction

**Pattern**:

```python

# Extract diff blocks from markdown

import re

diff_pattern = r'```suggestion\n(.*?)\n```'
diffs = re.findall(diff_pattern, comment, re.DOTALL)

```text

### 3. Rate Limit Handling

**Limits**: 5000 requests/hour per token

**Backoff strategy**:

```python

# Exponential backoff with jitter

import time
import random

def backoff_request(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait_time)

```text

## References

* [GitHub API docs](https://docs.github.com/rest)
* Project parsing code: `src/review_bot_automator/llm/parser.py`
```

**Time to create**: 2-3 hours
**Long-term value**: HIGH (institutional knowledge)

### Skill 2: Multi-Provider LLM Testing

Create `.claude/skills/multi-provider-llm-testing/SKILL.md`:

```markdown
---
name: "multi-provider-llm-testing"
description: "Test LLM providers (Anthropic, OpenAI, Ollama, Claude CLI, Codex CLI) systematically: mock responses, cost simulation, performance benchmarking, provider failover. Use when testing LLM integrations."
allowed-tools: ["mcp__ollama__ollama_chat", "mcp__ollama__ollama_list", "Read", "Write", "Bash(pytest:*)"]
---

# Multi-Provider LLM Testing Patterns

## When to Use
* Testing provider failover
* Mocking LLM responses
* Cost simulation
* Performance benchmarking
* Validating Issue #129 (Ollama integration)

## Test Patterns

### 1. Provider Health Check Mocking

```python

# Mock provider availability

import pytest
from unittest.mock import patch

@pytest.fixture
def mock_ollama_available():
    with patch('ollama.Client.list') as mock_list:
        mock_list.return_value = {'models': [{'name': 'qwen2.5-coder:7b'}]}
        yield mock_list

def test_ollama_provider_available(mock_ollama_available):
    from review_bot_automator.llm.factory import get_provider
    provider = get_provider("ollama")
    assert provider.is_available()

```text

### 2. API Response Fixtures

```python

# tests/fixtures/llm_responses.py

ANTHROPIC_RESPONSE = {
    "content": [{
        "type": "text",
        "text": '{"changes": [{"file": "test.py", "line": 10}]}'
    }],
    "usage": {"input_tokens": 100, "output_tokens": 50}
}

OPENAI_RESPONSE = {
    "choices": [{
        "message": {
            "content": '{"changes": [{"file": "test.py", "line": 10}]}'
        }
    }],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50}
}

OLLAMA_RESPONSE = {
    "message": {
        "content": '{"changes": [{"file": "test.py", "line": 10}]}'
    }
}

```text

### 3. Cost Calculation Tests

```python

def test_provider_cost_calculation():
    """Test cost tracking across providers."""
    from review_bot_automator.llm.providers import AnthropicProvider, OpenAIProvider

    # Anthropic pricing
    anthropic = AnthropicProvider(model="claude-sonnet-4-5")
    cost = anthropic.calculate_cost(input_tokens=1000, output_tokens=500)
    assert cost == pytest.approx(0.009)  # $3/MTok input + $15/MTok output

    # OpenAI pricing
    openai = OpenAIProvider(model="gpt-4o-mini")
    cost = openai.calculate_cost(input_tokens=1000, output_tokens=500)
    assert cost == pytest.approx(0.00045)  # $0.150/MTok input + $0.600/MTok output

```text

### 4. Performance Benchmarking

```python

import time
import pytest

@pytest.mark.benchmark
@pytest.mark.parametrize("provider_name", ["anthropic", "openai", "ollama"])
def test_provider_latency(provider_name, benchmark):
    """Benchmark provider response time."""
    from review_bot_automator.llm.factory import get_provider

    provider = get_provider(provider_name)
    test_prompt = "Parse this CodeRabbit comment: ..."

    def parse():
        return provider.parse(test_prompt)

    result = benchmark(parse)
    assert result is not None

```text

### 5. Provider Failover Testing

```python

def test_provider_failover():
    """Test automatic failover to backup provider."""
    from review_bot_automator.llm.factory import get_provider_with_fallback

    # Primary: Anthropic, Fallback: OpenAI
    provider = get_provider_with_fallback(
        primary="anthropic",
        fallback="openai"
    )

    # Simulate primary failure
    with patch.object(provider.primary, 'parse', side_effect=Exception("API Error")):
        result = provider.parse("test comment")
        assert result is not None  # Fallback succeeded

```text

## References

* Provider implementations: `src/review_bot_automator/llm/providers/`
* Test fixtures: `tests/fixtures/llm_responses.py`
* Issue #129: Ollama provider validation
```

**Time to create**: 3-4 hours
**Long-term value**: HIGH (critical for v2.0)

### Skill 3: Conflict Resolution ML

Create `.claude/skills/conflict-resolution-ml/SKILL.md`:

```markdown
---
name: "conflict-resolution-ml"
description: "Machine learning patterns for conflict resolution: training priority models, feature engineering from conflicts, user decision tracking, strategy effectiveness evaluation. Use when building ML-powered conflict resolution."
allowed-tools: ["Read", "Write", "Bash(python:*)"]
---

# Conflict Resolution ML Patterns

## When to Use
* Training priority models
* Feature engineering for conflicts
* User decision tracking
* Strategy effectiveness metrics
* A/B testing resolution approaches

## Core Concepts

### 1. Feature Extraction from Conflicts

```python

# Extract features from conflict pairs

def extract_conflict_features(conflict):
    """Extract ML features from conflict."""
    features = {
        # Code features
        'lines_changed': len(conflict.lines),
        'file_type': conflict.file_path.suffix,
        'indentation_level': conflict.indentation_depth,

        # Semantic features
        'is_import_statement': conflict.is_import,
        'is_function_def': conflict.is_function,
        'is_class_def': conflict.is_class,

        # Context features
        'surrounding_context_size': len(conflict.context_lines),
        'comment_quality_score': conflict.comment_quality,

        # Historical features
        'file_churn_rate': get_file_churn(conflict.file_path),
        'author_experience': get_author_stats(conflict.author),
    }
    return features

```text

### 2. User Decision Tracking

```python

# Track which resolutions users accept/reject

class ResolutionTracker:
    def __init__(self):
        self.decisions = []

    def record_decision(self, conflict, resolution, accepted):
        """Record user's decision on resolution."""
        self.decisions.append({
            'conflict_features': extract_conflict_features(conflict),
            'resolution_strategy': resolution.strategy,
            'accepted': accepted,
            'timestamp': datetime.now()
        })

    def export_training_data(self, path):
        """Export decisions for model training."""
        import pandas as pd
        df = pd.DataFrame(self.decisions)
        df.to_parquet(path)

```text

### 3. Priority Score Calculation

```python

# ML model for priority scoring

from sklearn.ensemble import RandomForestClassifier

class ConflictPriorityModel:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100)

    def train(self, training_data):
        """Train on historical decisions."""
        X = training_data['features']
        y = training_data['accepted']
        self.model.fit(X, y)

    def predict_priority(self, conflict):
        """Predict if resolution should be accepted."""
        features = extract_conflict_features(conflict)
        return self.model.predict_proba([features])[0][1]

```text

### 4. Strategy Effectiveness Metrics

```python

# Measure strategy performance

def evaluate_strategy(strategy_name, decisions):
    """Calculate metrics for resolution strategy."""
    strategy_decisions = [
        d for d in decisions
        if d['resolution_strategy'] == strategy_name
    ]

    total = len(strategy_decisions)
    accepted = sum(1 for d in strategy_decisions if d['accepted'])

    return {
        'strategy': strategy_name,
        'total_uses': total,
        'acceptance_rate': accepted / total if total > 0 else 0,
        'avg_confidence': np.mean([d['confidence'] for d in strategy_decisions]),
    }

```text

## Implementation Workflow

1. **Data Collection Phase**:
   * Track user decisions for 100+ conflicts
   * Record features and outcomes
   * Export training dataset

2. **Model Training Phase**:
   * Feature engineering
   * Train RandomForest classifier
   * Cross-validation (80/20 split)
   * Evaluate on holdout set

3. **Model Integration Phase**:
   * Load trained model in resolver
   * Use predictions to adjust priorities
   * Continuous monitoring of accuracy

4. **A/B Testing Phase**:
   * Control: Rule-based priorities
   * Treatment: ML-based priorities
   * Measure: acceptance rate, time saved

## References

* Priority strategy: `src/review_bot_automator/strategies/priority_strategy.py`
* Conflict models: `src/review_bot_automator/core/models.py`
* Future ML roadmap: `docs/planning/ROADMAP.md`
```

**Time to create**: 3-4 hours
**Long-term value**: HIGH (future feature)

---

## Usage Examples

### Python Development

**Optimize test suite:**

```text
Ask Claude: "Optimize our test suite using python-development patterns"

```

Claude will invoke `/python-development:python-testing-patterns` and analyze your test files.

**Profile performance:**

```text
Ask Claude: "Profile resolver.py for bottlenecks"

```

Claude will invoke `/python-development:python-performance-optimization src/review_bot_automator/core/resolver.py`

### LLM Application Development

**Improve prompts:**

```text
Ask Claude: "Optimize LLM prompts for parsing CodeRabbit comments"

```

Claude will invoke `/llm-application-dev:prompt-optimization src/review_bot_automator/llm/prompts/`

**Evaluate providers:**

```text
Ask Claude: "Compare Anthropic vs OpenAI vs Ollama quality"

```

Claude will invoke `/llm-application-dev:llm-evaluation` and run systematic tests.

### CI/CD Automation

**Optimize workflows:**

```text
Ask Claude: "Optimize security.yml workflow to reduce scan time"

```

Claude will invoke `/cicd-automation:github-actions-optimization .github/workflows/security.yml`

**Improve secrets handling:**

```text
Ask Claude: "Review secrets management in CI/CD"

```

Claude will invoke `/cicd-automation:secrets-management .github/workflows/`

### Custom Skills

**Use CodeRabbit patterns:**

```text
Ask Claude: "Parse this CodeRabbit review comment using our patterns"

```

Claude will invoke `coderabbit-api-patterns` skill.

**Test LLM providers:**

```text
Ask Claude: "Run multi-provider LLM tests"

```

Claude will invoke `multi-provider-llm-testing` skill.

---

## Troubleshooting

### Issue: Plugin Not Found

**Error**: `Plugin 'python-development' not found`

**Solution**:

1. Verify marketplace is added: `/plugin marketplace list`
2. If not, add marketplace: `/plugin marketplace add wshobson/agents`
3. Refresh marketplace: `/plugin marketplace refresh`
4. Retry installation

### Issue: Skill Not Invoked

**Problem**: Asked Claude to optimize code, but skill wasn't used

**Solution**:

1. Check skill description triggers (be more specific in request)
2. Explicitly mention skill: "Use python-development to optimize..."
3. Verify skill is installed: `/plugin list`

### Issue: Custom Skill Not Loading

**Problem**: Created custom skill but Claude doesn't see it

**Solution**:

1. Check file location: `.claude/skills/skill-name/SKILL.md`
2. Verify YAML frontmatter format
3. Restart Claude Code
4. Check skill description is clear and trigger-rich

### Issue: Context Window Bloat

**Problem**: Worried skills will use too many tokens

**Solution**:

* Skills use progressive disclosure (only load when invoked)
* Metadata is always loaded (minimal tokens)
* Full instructions loaded on-demand
* No impact unless skill is actively used

### Issue: Conflicting Skills

**Problem**: Multiple skills seem to do similar things

**Solution**:

* Skills don't conflict - they complement
* More specific request = better skill matching
* You can disable skills with: `/plugin uninstall skill-name`

---

## Success Metrics

Track these to measure impact:

### Quantitative

* **Time saved**: Log hours before/after skill usage
  * Target: 20+ hours/week
* **Test coverage**: 82.35% → 90%+
* **LLM parsing success**: 20% → 95%+
* **CI/CD build time**: 20-30% reduction
* **API costs**: 30-50% reduction (better prompts)

### Qualitative

* **Developer experience**: Less context switching
* **Code quality**: Fewer bugs in reviews
* **Documentation**: Always up-to-date
* **Security**: Faster vulnerability detection

---

## Additional Resources

* [skillsmp.com](https://skillsmp.com) - Skills marketplace
* [wshobson/agents](https://github.com/wshobson/agents) - Plugin repository
* [Claude Code docs](https://docs.claude.com/en/docs/claude-code/) - Official documentation
* Project docs: `docs/` directory

## See Also

* [MCP Servers Setup](MCP_SERVERS_SETUP.md) - GitHub MCP integration
* [Getting Started](getting-started.md) - Project setup
* [Configuration](configuration.md) - LLM provider setup
