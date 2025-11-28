# Review Bot Automator: LLM-First Refactor Roadmap

**Version:** 2.0
**Last Updated:** 2025-11-26
**Status:** 100% Complete - All Phases (0-6) Closed
**Target Release:** v2.0.0 (Released 2025-11-26)

> **📌 Important Note on Issue Numbers**:
> This document was created referencing issues #25-#31, but GitHub actually assigned issues #114-#120 for the LLM phases. When reading this document, interpret issue numbers as follows:
>
> * #25 → **#114** (Phase 0: Foundation)
> * #26 → **#115** (Phase 1: Basic LLM Parsing)
> * #27 → **#116** (Phase 2: Multi-Provider Support)
> * #28 → **#117** (Phase 3: CLI Integration Polish)
> * #29 → **#118** (Phase 4: Local Model Support)
> * #30 → **#119** (Phase 5: Optimization & Production Readiness)
> * #31 → **#120** (Phase 6: Documentation & Migration)
>
> All other references in this document remain accurate.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Audit](#2-current-state-audit)
3. [The Strategic Pivot](#3-the-strategic-pivot)
4. [Target Architecture](#4-target-architecture)
5. [Phase 0: Foundation](#5-phase-0-foundation-20-25-hours)
6. [Phase 1: Basic LLM Parsing](#6-phase-1-basic-llm-parsing-35-45-hours)
7. [Phase 2: Multi-Provider Support](#7-phase-2-multi-provider-support-25-30-hours)
8. [Phase 3: CLI Integration Polish](#8-phase-3-cli-integration-polish-15-20-hours)
9. [Phase 4: Local Model Support](#9-phase-4-local-model-support-15-20-hours)
10. [Phase 5: Optimization & Production Readiness](#10-phase-5-optimization--production-readiness-25-30-hours)
11. [Phase 6: Documentation & Migration](#11-phase-6-documentation--migration-15-20-hours)
12. [Risk Assessment & Mitigation](#12-risk-assessment--mitigation)
13. [Cost Analysis](#13-cost-analysis)
14. [Success Metrics](#14-success-metrics)
15. [Timeline & Milestones](#15-timeline--milestones)
16. [Appendices](#16-appendices)

---

## 1. Executive Summary

### 1.1 The Problem

The Review Bot Automator currently parses **only 20% of CodeRabbit comment formats** - specifically, fenced ```` ```suggestion```` blocks. Analysis of real PR data revealed:

* **60%** of CodeRabbit comments use ```` ```diff```` blocks
* **20%** use natural language descriptions
* **20%** use ```` ```suggestion```` blocks (our only supported format)

**Result:** We're missing **80% of CodeRabbit's suggestions**, rendering the tool ineffective for most use cases.

### 1.2 The Solution

Transform from a narrow **regex-only parser** to an **LLM-first universal parser** that understands all CodeRabbit comment formats:

* ✅ Diff blocks (`@@ -1,3 +1,3 @@`)
* ✅ Suggestion blocks (`` `suggestion` ``)
* ✅ Natural language ("change timeout from 30 to 60 seconds")
* ✅ Multi-option suggestions with rationales

### 1.3 Key Principles

1. **Backward Compatibility**: Feature flag OFF by default, no breaking changes
2. **User Choice**: Support 5 LLM providers (API-based, CLI-based, local)
3. **Preserve Quality**: Keep excellent security foundation (Phase 0, 95%+ test coverage)
4. **Incremental Rollout**: 6 phases over 10-12 weeks
5. **Cost Control**: Free tier options (CLI tools, local models) + caching

### 1.4 Project Scope

### Total Effort:**150-190 hours + 25% buffer =**188-238 hours

**Duration:**10-12 weeks (phased implementation)
**Testing Cost:** $50-100 in API costs
**Expected Outcome:** 5x increase in format coverage (20% → 100%)

### 1.5 Architecture at a Glance

```text
Before (v1.x):
GitHub Comments → Regex Parser → Change Objects → Conflict Resolution

After (v2.0):
GitHub Comments → [LLM Parser OR Regex Fallback] → Change Objects → Conflict Resolution
                   ↓
             User chooses provider:
             * Claude Code CLI (claude.ai subscription)
             * Codex CLI (chatgpt.com subscription)
             * OpenAI API (pay-per-token)
             * Anthropic API (pay-per-token)
             * Ollama (local, free)
```

### 1.6 Current Progress (As of 2025-11-21)

**Overall Status:** ~71% Complete (5/7 phases closed, Phases 5-6 in progress)

#### ✅ Completed Phases (Closed)

* **Phase 0: Foundation** ✅ CLOSED (Nov 6, 2025)
  * GitHub Issue: #114
  * PR: #121
  * Actual Effort: 20-25 hours
  * Deliverables: LLM data models, `CommentParser`, provider protocol, prompt engineering

* **Phase 1: Basic LLM Parsing** ✅ CLOSED (Nov 6, 2025)
  * GitHub Issue: #115
  * PR: #122
  * Actual Effort: 35-45 hours
  * Deliverables: OpenAI API provider, retry logic, cost tracking, 30+ tests

* **Phase 2: Multi-Provider Support** ✅ CLOSED (Nov 9, 2025)
  * GitHub Issue: #116
  * Actual Effort: 25-30 hours
  * Deliverables: All 5 providers (OpenAI, Anthropic, Claude CLI, Codex CLI, Ollama), GPU acceleration, HTTP pooling

* **Phase 3: CLI Integration Polish** ✅ CLOSED (Nov 11, 2025)
  * GitHub Issue: #117
  * Actual Effort: 15-20 hours
  * Deliverables: 5 presets, configuration precedence chain, enhanced error messages

* **Phase 4: Local Model Support** ✅ CLOSED (Nov 2025)
  * GitHub Issue: #118 (CLOSED)
  * Actual Effort: 15-20 hours
  * Completed Sub-Issues: 6/6
    * ✅ #167: HTTP connection pooling (Nov 12, 2025) - PR #173
    * ✅ #168: Model auto-download (Nov 12, 2025) - PR #175
    * ✅ #169: GPU acceleration (Nov 14, 2025) - PR #176
    * ✅ #170: Performance benchmarking - PR #199
    * ✅ #171: Privacy documentation - PR #201
    * ✅ #172: Offline integration tests
  * Deliverables: GPU detection (NVIDIA/AMD/Apple), privacy docs, benchmarking infrastructure

#### 🔄 In Progress

* **Phase 5: Optimization & Production Readiness** (Issue #119)
  * Status: Not started
  * Estimated: 25-30 hours

* **Phase 6: Documentation & Migration** (Issue #120 - ~50% complete)
  * Core LLM docs done, remaining: provider selection guide, cost analysis, API reference updates
  * Estimated: 15-20 hours total, ~7-10 hours remaining

**Total Effort to Date:** ~110-140 hours (of 150-190 estimated)
**Remaining Effort:** ~40-50 hours
**Estimated Completion:** 1-2 weeks at current velocity

---

## 2. Current State Audit

### 2.1 Codebase Inventory

**Total Source Code:** 7,481 lines of Python across 19 modules
**Test Coverage:** 82.35% overall, 95%+ on security modules
**Phase 0 (Security):**100% complete (committed 2025-11-03)

### 2.2 Module Analysis

#### **Keep As-Is (56% - 4,200 LOC)**

These modules work perfectly and need NO changes:

| Module | Purpose | LOC | Status |
| -------- | --------- | ----- | -------- |
| `security/input_validator.py` | Path traversal prevention, validation | 596 | ✅ Keep |
| `security/secure_file_handler.py` | Atomic file ops, permissions | 222 | ✅ Keep |
| `security/secret_scanner.py` | Secret detection (17 patterns) | 410 | ✅ Keep |
| `security/config.py` | Security configuration | 191 | ✅ Keep |
| `handlers/json_handler.py` | JSON file manipulation | 465 | ✅ Keep |
| `handlers/yaml_handler.py` | YAML file manipulation | 487 | ✅ Keep |
| `handlers/toml_handler.py` | TOML file manipulation | 517 | ✅ Keep |
| `handlers/base.py` | Handler interface | 341 | ✅ Keep |
| `analysis/conflict_detector.py` | Conflict detection engine | ~250 | ✅ Keep |
| `strategies/priority_strategy.py` | Priority-based resolution | 310 | ✅ Keep |
| `strategies/base.py` | Strategy interface | 34 | ✅ Keep |
| `core/rollback.py` | Git-based rollback | ~150 | ✅ Keep |
| `utils/path_utils.py` | Path utilities | 107 | ✅ Keep |
| `utils/text.py` | Text normalization | 17 | ✅ Keep |

#### **Modify/Extend (33% - 2,500 LOC)**

These modules need LLM integration:

| Module | Changes Needed | LOC | Impact |
| -------- | ---------------- | ----- | -------- |
| `core/resolver.py` | Add LLM parser integration | 1,184 | Medium |
| `core/models.py` | Add LLM metadata fields | 153 | Low |
| `integrations/github.py` | Store raw comments for LLM | 316 | Low |
| `config/runtime_config.py` | Add LLM configuration | 536 | Medium |
| `config/presets.py` | Add LLM presets | ~100 | Low |
| `cli/main.py` | Add LLM-related flags | ~400 | Medium |

#### **Replace (1% - 100 LOC)**

* Current regex-only `_parse_comment_suggestions()` in `resolver.py` (lines 198-244)
* Will be superseded by LLM parser with regex fallback

#### **New Code (11% - 800 LOC estimated)**

* `llm/` module: Provider abstraction, parsers, caching, cost tracking

### 2.3 Current Parsing Capabilities

**What Works Today:**

```python
# In resolver.py: _parse_comment_suggestions()
# Lines 198-244

suggestion_pattern = re.compile(r"```suggestion\s*\n(.*?)\n```", re.DOTALL)

```

**Supported Format:**

```markdown
**Option A:**

```suggestion

def foo():
    return "bar"

```text

```

**Unsupported Formats (80% of comments):**

```markdown
<!-- Diff Block -->
Apply this diff:

```diff

@@ -10,3 +10,3 @@ def calculate():

*    timeout = 30
+    timeout = 60

```text

<!-- Natural Language -->
In the `calculate_total()` function, change the discount from 10% to 15%.

<!-- Multi-Option -->
**Option 1:** Use async/await
**Option 2:** Use threading
**Option 3:** Keep synchronous

```

### 2.4 Critical Gap Analysis

**Conclusion:** The system is fundamentally limited by its parsing strategy, not its conflict resolution or application logic.

### 2.5 What Must Be Preserved

**Non-Negotiable Assets:**

1. **Security Foundation (Phase 0 - 100% Complete)**
   * Input validation, secret scanning, secure file operations
   * Test coverage: 95%+ on security modules
   * Zero regressions allowed

2. **Conflict Detection Engine**
   * Format-agnostic (works with any `Change` objects)
   * 5 conflict types: exact, major, partial, minor, semantic
   * Proven accuracy

3. **Priority System**
   * User selections: 100, Security: 90, Syntax: 80, Regular: 50
   * Works downstream of parsing

4. **File Handlers**
   * JSON, YAML, TOML structure-aware merging
   * Comment preservation, format preservation
   * Battle-tested

5. **Rollback System**
   * Git-based checkpointing
   * Automatic rollback on failure
   * Zero data loss

6. **Application Modes**
   * `all`, `conflicts-only`, `non-conflicts-only`, `dry-run`
   * Already implemented (Phase 2 complete)

7. **Test Coverage**
   * 82.35% overall
   * Must maintain > 80% throughout refactor

---

## 3. The Strategic Pivot

### 3.1 From Conflict Resolver to Suggestion Applier

### Old Mental Model

> "We resolve conflicts when multiple suggestions overlap."

**Problem:** Conflicts are rare (~5% of PRs). Most CodeRabbit comments are individual suggestions.

### New Mental Model

> "We parse and apply ALL CodeRabbit suggestions. When conflicts occur (edge case), we resolve them intelligently."

**Impact:** This pivot expands the tool's purpose from a niche conflict handler to a universal suggestion applier.

### 3.2 Why LLM-First

**Regex Limitations:**

1. **Rigid Pattern Matching:** Can't understand context or intent
2. **Format Brittleness:** New formats = new regex patterns
3. **No Semantic Understanding:** Can't parse natural language
4. **Maintenance Burden:** Each format needs custom parsing logic

**LLM Advantages:**

1. **Universal Adapter:** Understands all formats (diff, suggestion, prose)
2. **Context Awareness:** Can infer line numbers from function names
3. **Semantic Validation:** Can assess if a change makes sense
4. **Future-Proof:** New formats work automatically
5. **Metadata Enrichment:** Can extract rationale, confidence, risk level

**Trade-offs:**

| Aspect | Regex | LLM |
| -------- | ------- | ----- |
| **Accuracy** | 100% (for known formats) | 90-95% (structured output) |
| **Coverage** | 20% (only ```suggestion) | 100% (all formats) |
| **Cost** | Free | $0-$1.50 per 1K comments |
| **Latency** | < 1ms | 2-5s per comment |
| **Offline** | Yes | Depends (local models yes) |

**Decision:** LLM-first with regex fallback provides best of both worlds.

### 3.3 User-Driven Provider Selection

**Philosophy:** Let users choose based on their preferences:

* **Subscription-based (zero marginal cost):** Claude Code CLI, Codex CLI
* **API-based (pay-per-use):** OpenAI, Anthropic
* **Local (free, private):** Ollama

**No Forced Hierarchy:** We don't decide what's "best" - users do.

**Configuration Example:**

```yaml
# User Choice 1: Developer with claude.ai subscription
llm:
  provider: claude-cli
  model: claude-sonnet-4-5
# Cost: $0 (covered by subscription)

# User Choice 2: Enterprise with API budget
llm:
  provider: anthropic-api
  model: claude-haiku-4-5
  api_key: ${ANTHROPIC_API_KEY}
# Cost: ~$1.21 per 1K comments

# User Choice 3: Privacy-conscious team
llm:
  provider: ollama
  model: qwen2.5-coder:32b
# Cost: $0 (local inference)

```

---

## 4. Target Architecture

### 4.1 System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    GitHub PR Comments                       │
│       (All formats: diff, suggestion, natural language)     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Comment Storage (Raw)                          │
│         Store unprocessed comment for LLM context           │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴──────────┐
         │   Parsing Strategy   │
         │   Decision Point     │
         │  (Feature Flag)      │
         └───────────┬──────────┘
                     │
         ┌───────────┴──────────┐
         ▼                      ▼
┌──────────────────┐   ┌──────────────────┐
│  Regex Parser    │   │   LLM Parser     │
│  (Fallback)      │   │   (Primary)      │
│  ```suggestion   │   │  All formats     │
│                  │   │  via providers:  │
│  - Fast          │   │  - Claude CLI    │
│  - Free          │   │  - Codex CLI     │
│  - Limited       │   │  - OpenAI API    │
│                  │   │  - Anthropic API │
│                  │   │  - Ollama        │
└─────────┬────────┘   └────────┬─────────┘
          │                     │
          └──────────┬──────────┘
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Standardized Change Objects                    │
│  (path, start_line, end_line, content, metadata)           │
│  UNCHANGED INTERFACE - downstream code unaffected          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Conflict Detection Engine                      │
│  (Unchanged - format-agnostic, works with any Changes)     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         (Rest of pipeline unchanged)
         [Priority System → Resolution → Application → Rollback]

```

### 4.2 New Module Structure

```text
src/review_bot_automator/llm/         # NEW MODULE (~800 LOC)
├── __init__.py                        # Package initialization
├── base.py                            # Abstract interfaces (100 LOC)
│   ├── LLMProvider (Protocol)
│   ├── LLMParser (ABC)
│   └── ParsedChange (dataclass)
├── prompt_templates.py                # Prompt engineering (150 LOC)
│   ├── PARSE_COMMENT_PROMPT
│   ├── PARSE_DIFF_BLOCK_PROMPT
│   └── PARSE_NATURAL_LANGUAGE_PROMPT
├── providers/                         # Provider implementations
│   ├── __init__.py                    # Provider factory
│   ├── anthropic_api.py               # Claude API (120 LOC)
│   ├── openai_api.py                  # GPT API (120 LOC)
│   ├── claude_cli.py                  # Claude Code CLI (100 LOC)
│   ├── codex_cli.py                   # Codex CLI (100 LOC)
│   └── ollama.py                      # Local Ollama (100 LOC)
├── parser.py                          # LLM-powered parser (150 LOC)
│   └── UniversalLLMParser
├── cache.py                           # Response caching (80 LOC)
│   └── LLMResponseCache
└── cost_tracker.py                    # Token/cost tracking (80 LOC)
    └── CostTracker

```

### 4.3 Integration Points

**Key Modification: `core/resolver.py`**

```python
# Line 133-196: extract_changes_from_comments()

# BEFORE (v1.x)
def extract_changes_from_comments(self, comments: list[dict[str, Any]]) -> list[Change]:
    """Extract changes using regex."""
    changes = []
    for comment in comments:
        # ... parse with _parse_comment_suggestions() ...
    return changes

# AFTER (v2.0)
def extract_changes_from_comments(self, comments: list[dict[str, Any]]) -> list[Change]:
    """Extract changes using LLM or regex based on config."""
    if self.config.get("llm_enabled", False):
        return self._extract_changes_with_llm(comments)
    else:
        return self._extract_changes_with_regex(comments)  # Existing logic

def _extract_changes_with_llm(self, comments: list[dict[str, Any]]) -> list[Change]:
    """NEW: Extract changes using LLM parser."""
    from review_bot_automator.llm.parser import UniversalLLMParser
    from review_bot_automator.llm.providers import create_provider

    # Initialize provider based on config
    provider = create_provider(self.config)
    parser = UniversalLLMParser(provider, fallback_to_regex=True)

    # Parse each comment
    changes = []
    for comment in comments:
        try:
            parsed_changes = parser.parse_comment(
                comment_body=comment.get("body", ""),
                file_path=comment.get("path"),
            )
            # Convert ParsedChange → Change objects
            for parsed in parsed_changes:
                change = self._convert_parsed_to_change(parsed, comment)
                changes.append(change)
        except Exception as e:
            self.logger.warning(f"LLM parsing failed for comment {comment.get('id')}: {e}")
            # Fallback to regex for this comment
            changes.extend(self._parse_single_comment_with_regex(comment))

    return changes

```

**Extension: `core/models.py`**

```python
# Line 90-101: Change dataclass

@dataclass(frozen=True, slots=True)
class Change:
    """Represents a single change suggestion."""

    # EXISTING FIELDS (unchanged)
    path: str
    start_line: int
    end_line: int
    content: str
    metadata: ChangeMetadata | Mapping[str, object]
    fingerprint: str
    file_type: FileType

    # NEW FIELDS (backward compatible with default values)
    llm_confidence: float | None = None           # 0.0-1.0 confidence score
    llm_provider: str | None = None               # "claude", "gpt-5", etc.
    parsing_method: str = "regex"                 # "regex" | "llm"
    change_rationale: str | None = None           # Why this change
    risk_level: str | None = None                 # "low" | "medium" | "high"

```

**Extension: `config/runtime_config.py`**

```python
# Line 46-76: RuntimeConfig dataclass

@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Runtime configuration for the resolver."""

    # EXISTING FIELDS (unchanged)
    mode: ApplicationMode
    enable_rollback: bool
    validate_before_apply: bool
    parallel_processing: bool
    max_workers: int

    # NEW FIELDS (LLM configuration)
    llm_enabled: bool = False                     # Feature flag (default: OFF)
    llm_provider: str = "claude-cli"              # Provider selection
    llm_model: str = "claude-sonnet-4-5"          # Model name
    llm_api_key: str | None = None                # API key (if needed)
    llm_fallback_to_regex: bool = True            # Safety fallback
    llm_cache_enabled: bool = True                # Cache LLM responses
    llm_max_tokens: int = 2000                    # Token limit per request
    llm_cost_budget: float | None = None          # Max cost per run (USD)

```

### 4.4 Backward Compatibility Strategy

**Feature Flag Approach:**

1. **Default Behavior:** LLM parsing **DISABLED** by default
   * Existing users see no change
   * Must opt-in via `--llm` flag or `CR_LLM_ENABLED=true`

2. **Graceful Degradation:**
   * If LLM provider unavailable → fallback to regex
   * If LLM parsing fails → fallback to regex
   * Log warnings, don't fail hard

3. **Data Model Compatibility:**
   * New fields have default values
   * Old code ignores new fields
   * Serialization/deserialization handles both formats

4. **No Breaking Changes:**
   * CLI commands identical (new flags are optional)
   * API signatures unchanged (new parameters have defaults)
   * Configuration files v1.x work in v2.0

---

## 5. Phase 0: Foundation (20-25 hours)

**Goal:** Set up infrastructure without changing behavior.

**GitHub Issue:** #25
**Milestone:** v2.0 - LLM-First Architecture
**Dependencies:** None
**Estimated Effort:** 20-25 hours

### 5.1 Tasks

#### Task 0.1: Create LLM Module Structure (3 hours)

**Create new files:**

```bash
touch src/review_bot_automator/llm/__init__.py
touch src/review_bot_automator/llm/base.py
touch src/review_bot_automator/llm/prompt_templates.py
touch src/review_bot_automator/llm/parser.py
touch src/review_bot_automator/llm/cache.py
touch src/review_bot_automator/llm/cost_tracker.py
mkdir src/review_bot_automator/llm/providers
touch src/review_bot_automator/llm/providers/__init__.py

```

**Implement `base.py`:**

```python
"""Abstract interfaces for LLM integration.

This module defines the core protocols and data structures for LLM-powered
comment parsing. All provider implementations must conform to these interfaces.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

@dataclass(frozen=True, slots=True)
class ParsedChange:
    """Structured output from LLM parser.

    Represents a single code change extracted by an LLM from a GitHub comment.
    This is an intermediate format that gets converted to the standard Change
    dataclass by the resolver.
    """

    file_path: str                    # Path to file being modified
    start_line: int                   # Starting line number
    end_line: int                     # Ending line number
    new_content: str                  # The actual code to apply
    change_type: str                  # "addition", "modification", "deletion"
    confidence: float                 # 0.0-1.0 (LLM's confidence in extraction)
    rationale: str                    # Why this change is suggested
    risk_level: str = "low"           # "low", "medium", "high"

@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers.

    All LLM backend implementations (API-based, CLI-based, local) must
    implement this protocol to ensure consistent behavior.
    """

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate completion from prompt.

        Args:
            prompt: Input prompt for the LLM
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text (typically JSON for structured output)

        Raises:
            RuntimeError: If generation fails
        """
        ...

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Used for cost estimation and tracking.

        Args:
            text: Text to tokenize

        Returns:
            Number of tokens
        """
        ...

class LLMParser(ABC):
    """Abstract base for LLM-powered parsers."""

    @abstractmethod
    def parse_comment(
        self,
        comment_body: str,
        file_path: str | None = None
    ) -> list[ParsedChange]:
        """Parse a GitHub comment using LLM.

        Args:
            comment_body: Raw comment text from GitHub
            file_path: Optional file path for context

        Returns:
            List of extracted changes

        Raises:
            RuntimeError: If parsing fails and no fallback available
        """
        ...

```

#### Task 0.2: Add Configuration Support (4 hours)

**Modify `config/runtime_config.py`:**

```python
# Add to existing RuntimeConfig dataclass

    # LLM Configuration (Phase 0)
    llm_enabled: bool = False
    llm_provider: str = "claude-cli"
    llm_model: str = "claude-sonnet-4-5"
    llm_api_key: str | None = None
    llm_fallback_to_regex: bool = True
    llm_cache_enabled: bool = True
    llm_max_tokens: int = 2000
    llm_cost_budget: float | None = None

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        """Load configuration from environment variables."""
        # ... existing code ...

        # NEW: Load LLM config from environment
        llm_enabled = os.getenv("CR_LLM_ENABLED", "false").lower() == "true"
        llm_provider = os.getenv("CR_LLM_PROVIDER", "claude-cli")
        llm_model = os.getenv("CR_LLM_MODEL", "claude-sonnet-4-5")
        llm_api_key = os.getenv("CR_LLM_API_KEY")

        return cls(
            # ... existing fields ...
            llm_enabled=llm_enabled,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
        )

```

**Update `.env.example`:**

```bash
# LLM Parsing Configuration (Phase 0)
CR_LLM_ENABLED=false                    # Enable LLM parsing (default: false)
CR_LLM_PROVIDER=claude-cli              # Provider: claude-cli, openai, anthropic-api, ollama, codex-cli
CR_LLM_MODEL=claude-sonnet-4-5          # Model name (provider-specific)
CR_LLM_API_KEY=                         # API key (if using API provider)
CR_LLM_FALLBACK=true                    # Fallback to regex on LLM failure
CR_LLM_CACHE_ENABLED=true               # Cache LLM responses
CR_LLM_MAX_TOKENS=2000                  # Max tokens per request
CR_LLM_COST_BUDGET=                     # Max cost per run (USD, optional)

```

#### Task 0.3: Update Data Models (3 hours)

**Modify `core/models.py`:**

```python
@dataclass(frozen=True, slots=True)
class Change:
    """Represents a single change suggestion."""

    # Existing fields (unchanged)
    path: str
    start_line: int
    end_line: int
    content: str
    metadata: ChangeMetadata | Mapping[str, object]
    fingerprint: str
    file_type: FileType

    # NEW: LLM metadata fields (backward compatible)
    llm_confidence: float | None = None
    llm_provider: str | None = None
    parsing_method: str = "regex"
    change_rationale: str | None = None
    risk_level: str | None = None

```

**Write backward compatibility tests:**

```python
# tests/unit/test_models_backward_compat.py

def test_change_backward_compatible_construction():
    """Test that Change can be constructed without new LLM fields."""
    change = Change(
        path="file.py",
        start_line=1,
        end_line=5,
        content="new code",
        metadata={},
        fingerprint="abc123",
        file_type=FileType.PYTHON,
        # Note: NOT providing llm_* fields
    )

    assert change.llm_confidence is None
    assert change.llm_provider is None
    assert change.parsing_method == "regex"
    assert change.change_rationale is None
    assert change.risk_level is None

def test_change_serialization_backward_compat():
    """Test that serialization works with both old and new formats."""
    # Old format (no LLM fields)
    old_data = {
        "path": "file.py",
        "start_line": 1,
        "end_line": 5,
        "content": "code",
        "metadata": {},
        "fingerprint": "abc",
        "file_type": "python",
    }

    # Should deserialize successfully
    change = Change(**old_data)
    assert change.parsing_method == "regex"

```

#### Task 0.4: Add Feature Flag Plumbing (3 hours)

**Modify `cli/main.py`:**

```python
@apply_cmd.command()
@click.option("--owner", required=True, help="Repository owner")
@click.option("--repo", required=True, help="Repository name")
@click.option("--pr", type=int, required=True, help="Pull request number")
@click.option("--mode",
              type=click.Choice(["all", "conflicts-only", "non-conflicts-only", "dry-run"]),
              default="all")
# NEW: LLM options
@click.option("--llm/--no-llm", default=False, help="Enable LLM parsing (default: disabled)")
@click.option("--llm-provider",
              type=click.Choice(["claude-cli", "openai", "anthropic-api", "ollama", "codex-cli"]),
              default="claude-cli",
              help="LLM provider to use")
@click.option("--llm-model", type=str, help="LLM model name (provider-specific)")
def apply(owner: str, repo: str, pr: int, mode: str, llm: bool, llm_provider: str, llm_model: str | None):
    """Apply suggestions from a PR."""

    # Build config with LLM options
    config = {
        "mode": mode,
        "llm_enabled": llm,
        "llm_provider": llm_provider,
    }
    if llm_model:
        config["llm_model"] = llm_model

    # ... rest of command ...

```

#### Task 0.5: Set Up Test Infrastructure (4 hours)

**Create test directory:**

```bash
mkdir tests/llm
touch tests/llm/__init__.py
touch tests/llm/test_base.py
touch tests/llm/test_parser.py
mkdir tests/fixtures/llm

```

**Create test fixtures:**

```bash
# tests/fixtures/llm/comments_diff_blocks.json
# Real CodeRabbit comments with diff blocks

# tests/fixtures/llm/comments_natural_language.json
# Real CodeRabbit comments with prose suggestions

# tests/fixtures/llm/llm_responses/
# Cached LLM responses for testing

```

**Write mock utilities:**

```python
# tests/llm/conftest.py

import pytest
from review_bot_automator.llm.base import LLMProvider

class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.call_count = 0

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Return pre-programmed response."""
        self.call_count += 1
        return self.responses.get("default", '[]')

    def count_tokens(self, text: str) -> int:
        """Mock token counting."""
        return len(text.split())

@pytest.fixture
def mock_llm_provider():
    """Fixture for mock LLM provider."""
    return MockLLMProvider({
        "default": '[{"file_path": "test.py", "start_line": 1, "end_line": 1, ...}]'
    })

```

#### Task 0.6: Add Dependencies (3 hours)

**Update `pyproject.toml`:**

```toml
[project.optional-dependencies]
llm = [
    "anthropic>=0.40.0",          # Claude API
    "openai>=1.58.1",              # GPT API
    "httpx>=0.28.1",               # HTTP client for Ollama
    "tenacity>=9.0.0",             # Retry logic
    "tiktoken>=0.9.0",             # Token counting (OpenAI)
]

[project]
dependencies = [
    # ... existing dependencies ...
]

```

**Test installation:**

```bash
pip install -e ".[llm]"
python -c "import anthropic, openai, httpx, tenacity, tiktoken; print('LLM dependencies OK')"

```

### 5.2 Deliverables

* [ ] `llm/` module structure created
* [ ] `RuntimeConfig` extended with LLM fields
* [ ] `Change` model extended (backward compatible)
* [ ] Feature flag infrastructure (`--llm` CLI flag)
* [ ] Test infrastructure ready (`tests/llm/`, fixtures, mocks)
* [ ] Dependencies added and tested
* [ ] All existing tests still pass
* [ ] Backward compatibility tests pass

### 5.3 Success Criteria

* ✅ Feature flag can be toggled (no-op currently)
* ✅ Config validation works for LLM options
* ✅ No regression in existing functionality
* ✅ Test coverage maintained at 80%+
* ✅ Documentation updated (inline docstrings)

### 5.4 Testing

```bash
# Run existing test suite (should all pass)
pytest tests/ --cov=src --cov-report=term-missing

# Run new backward compat tests
pytest tests/unit/test_models_backward_compat.py -v

# Verify feature flag
pr-resolve apply --owner test --repo test --pr 1 --llm --help
# Should show LLM options but not fail

```

---

## 6. Phase 1: Basic LLM Parsing (35-45 hours)

**Goal:** Get one LLM provider working end-to-end.

**GitHub Issue:** #26
**Milestone:** v2.0 - LLM-First Architecture
**Dependencies:** Phase 0 (#25)
**Estimated Effort:** 35-45 hours

### 6.1 Tasks

#### Task 1.1: Implement Abstract Parser Interface (5 hours)

**File:** `src/review_bot_automator/llm/base.py`

(Already created in Phase 0, but enhance with full implementation)

#### Task 1.2: Design Prompt Templates (8 hours)

**File:** `src/review_bot_automator/llm/prompt_templates.py`

**Research and design prompts for:**

1. Diff block parsing (`@@ -1,3 +1,3 @@`)
2. Suggestion block parsing (`` `suggestion` ``)
3. Natural language parsing ("change X to Y")
4. Multi-option parsing ("**Option 1:** ...")

**Example prompt (simplified):**

```python
PARSE_COMMENT_PROMPT = """You are a code change extractor analyzing GitHub PR comments from CodeRabbit AI.

Your task: Extract ALL suggested code changes from the comment below.

Comment format can be:
1. Diff blocks: ```diff @@ -1,3 +1,3 @@ ...```
2. Suggestion blocks: ```suggestion code here```
3. Natural language: "change the timeout from 30 to 60 seconds"
4. Multiple options: **Option 1:** ... **Option 2:** ...

File context: {file_path}
Line context: {line_number}

Comment body:

```

{comment_body}

```text

Extract changes in this JSON array format:
[
  {{
    "file_path": "path/to/file.py",
    "start_line": 10,
    "end_line": 15,
    "new_content": "the actual code to apply",
    "change_type": "modification",
    "confidence": 0.95,
    "rationale": "why this change is suggested",
    "risk_level": "low"
  }}
]

Rules:
1. Extract from ALL formats (diff, suggestion, prose)
2. For diff blocks, parse @@ line numbers accurately
3. For natural language, infer line numbers from context (set confidence < 0.7 if uncertain)
4. If line numbers are unclear, return confidence < 0.5
5. Return empty array [] if no changes found
6. confidence must be 0.0-1.0 float
7. change_type must be: "addition", "modification", or "deletion"
8. risk_level must be: "low", "medium", or "high"

Output ONLY valid JSON array, no markdown, no explanation.
"""

```

**Test prompts with real API:**

```python
# tests/llm/test_prompts.py

@pytest.mark.integration
def test_parse_diff_block_with_real_api():
    """Test prompt with real Claude API (integration test)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    provider = ClaudeAPIProvider(api_key)
    prompt = PARSE_COMMENT_PROMPT.format(
        comment_body=SAMPLE_DIFF_COMMENT,
        file_path="test.py",
        line_number=10,
    )

    response = provider.generate(prompt, max_tokens=2000)
    parsed = json.loads(response)

    assert isinstance(parsed, list)
    assert len(parsed) > 0
    assert "file_path" in parsed[0]

```

#### Task 1.3: Implement Claude API Provider (10 hours)

**File:** `src/review_bot_automator/llm/providers/anthropic_api.py`

**Full implementation with:**

* Retry logic (exponential backoff)
* Rate limiting
* Error handling
* Token counting
* Cost tracking

```python
"""Anthropic Claude API provider implementation."""

import logging
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from review_bot_automator.llm.base import LLMProvider

logger = logging.getLogger(__name__)

class ClaudeAPIProvider:
    """Claude API provider implementation.

    Provides access to Anthropic's Claude models via their API.
    Requires ANTHROPIC_API_KEY environment variable or explicit api_key.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        timeout: int = 60,
    ):
        """Initialize Claude API provider.

        Args:
            api_key: Anthropic API key
            model: Model identifier (e.g., "claude-sonnet-4-20250514")
            timeout: Request timeout in seconds
        """
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self.model = model
        self.total_tokens_used = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((anthropic.APITimeoutError, anthropic.RateLimitError)),
    )
    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate completion with retry logic.

        Retries on:
        * API timeout errors
        * Rate limit errors

        Does NOT retry on:
        * Authentication errors
        * Invalid request errors

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text (typically JSON)

        Raises:
            RuntimeError: If generation fails after retries
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.0,  # Deterministic for consistency
            )

            # Track token usage
            self.total_tokens_used += response.usage.input_tokens + response.usage.output_tokens

            logger.debug(
                f"Claude API call: {response.usage.input_tokens} input + "
                f"{response.usage.output_tokens} output tokens"
            )

            return response.content[0].text

        except anthropic.AuthenticationError as e:
            logger.error(f"Claude authentication failed: {e}")
            raise RuntimeError(f"Claude API authentication error: {e}") from e

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            raise RuntimeError(f"Claude API error: {e}") from e

    def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's tokenizer.

        Args:
            text: Text to tokenize

        Returns:
            Number of tokens
        """
        # Anthropic provides token counting via API
        return self.client.count_tokens(text)

```

#### Task 1.4: Implement LLM Parser (8 hours)

**File:** `src/review_bot_automator/llm/parser.py`

**Full implementation:**

```python
"""LLM-powered universal comment parser."""

import json
import logging
from typing import Any

from review_bot_automator.llm.base import LLMParser, ParsedChange, LLMProvider
from review_bot_automator.llm.prompt_templates import PARSE_COMMENT_PROMPT

logger = logging.getLogger(__name__)

class UniversalLLMParser(LLMParser):
    """LLM-powered universal comment parser.

    Parses all CodeRabbit comment formats:
    * Diff blocks (```diff)
    * Suggestion blocks (```suggestion)
    * Natural language descriptions
    * Multi-option suggestions
    """

    def __init__(
        self,
        provider: LLMProvider,
        fallback_to_regex: bool = True,
        confidence_threshold: float = 0.5,
    ):
        """Initialize parser.

        Args:
            provider: LLM provider instance
            fallback_to_regex: If True, return empty list on failure (triggers regex fallback)
            confidence_threshold: Minimum confidence to accept change (0.0-1.0)
        """
        self.provider = provider
        self.fallback_to_regex = fallback_to_regex
        self.confidence_threshold = confidence_threshold

    def parse_comment(
        self,
        comment_body: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ) -> list[ParsedChange]:
        """Parse comment using LLM.

        Args:
            comment_body: Raw comment text
            file_path: Optional file path for context
            line_number: Optional line number for context

        Returns:
            List of extracted changes (empty if parsing failed and fallback enabled)

        Raises:
            RuntimeError: If parsing fails and fallback_to_regex=False
        """
        try:
            # Build prompt with context
            prompt = PARSE_COMMENT_PROMPT.format(
                comment_body=comment_body,
                file_path=file_path or "unknown",
                line_number=line_number or "unknown",
            )

            # Generate response
            response = self.provider.generate(prompt, max_tokens=2000)

            # Parse JSON response
            try:
                changes_data = json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(f"LLM returned invalid JSON: {response[:200]}...")
                raise RuntimeError(f"Invalid JSON from LLM: {e}") from e

            if not isinstance(changes_data, list):
                logger.error(f"LLM returned non-list: {type(changes_data)}")
                raise RuntimeError(f"LLM must return JSON array, got {type(changes_data)}")

            # Convert to ParsedChange objects
            parsed_changes = []
            for change_dict in changes_data:
                try:
                    change = ParsedChange(**change_dict)

                    # Filter by confidence threshold
                    if change.confidence < self.confidence_threshold:
                        logger.warning(
                            f"Skipping change with low confidence: {change.confidence} < {self.confidence_threshold}"
                        )
                        continue

                    parsed_changes.append(change)

                except TypeError as e:
                    logger.warning(f"Invalid change format from LLM: {change_dict}: {e}")
                    continue

            logger.info(f"LLM parsed {len(parsed_changes)} changes from comment (confidence >= {self.confidence_threshold})")
            return parsed_changes

        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")

            if self.fallback_to_regex:
                logger.info("Returning empty list to trigger regex fallback")
                return []
            else:
                raise RuntimeError(f"LLM parsing failed: {e}") from e

```

#### Task 1.5: Integrate into Resolver (6 hours)

**Modify:** `src/review_bot_automator/core/resolver.py`

```python
def extract_changes_from_comments(self, comments: list[dict[str, Any]]) -> list[Change]:
    """Extract changes using LLM or regex based on config."""

    # Check if LLM enabled
    if self.config.get("llm_enabled", False):
        try:
            return self._extract_changes_with_llm(comments)
        except Exception as e:
            self.logger.error(f"LLM extraction failed: {e}")
            if self.config.get("llm_fallback_to_regex", True):
                self.logger.info("Falling back to regex parser")
                return self._extract_changes_with_regex(comments)
            raise
    else:
        return self._extract_changes_with_regex(comments)

def _extract_changes_with_llm(self, comments: list[dict[str, Any]]) -> list[Change]:
    """Extract changes using LLM parser.

    NEW METHOD - Phase 1
    """
    from review_bot_automator.llm.parser import UniversalLLMParser
    from review_bot_automator.llm.providers.anthropic_api import ClaudeAPIProvider

    # Initialize provider
    api_key = self.config.get("llm_api_key") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "LLM parsing enabled but ANTHROPIC_API_KEY not set. "
            "Set via environment variable or config."
        )

    model = self.config.get("llm_model", "claude-sonnet-4-20250514")
    provider = ClaudeAPIProvider(api_key, model=model)

    fallback = self.config.get("llm_fallback_to_regex", True)
    parser = UniversalLLMParser(provider, fallback_to_regex=fallback)

    changes = []
    for comment in comments:
        body = comment.get("body", "")
        path = comment.get("path")
        line = comment.get("line") or comment.get("original_line")

        # Parse with LLM
        try:
            parsed_changes = parser.parse_comment(body, path, line)

            # Convert ParsedChange → Change objects
            for parsed in parsed_changes:
                change = self._convert_parsed_to_change(parsed, comment)
                changes.append(change)

        except Exception as e:
            self.logger.warning(f"LLM parsing failed for comment {comment.get('id')}: {e}")
            # If fallback enabled, try regex for this comment
            if fallback:
                regex_changes = self._parse_single_comment_with_regex(comment)
                changes.extend(regex_changes)

    # If LLM returned nothing, fallback to regex for all comments
    if not changes and fallback:
        self.logger.info("LLM returned no changes, using regex fallback for all comments")
        return self._extract_changes_with_regex(comments)

    return changes

def _convert_parsed_to_change(self, parsed: ParsedChange, comment: dict[str, Any]) -> Change:
    """Convert ParsedChange (LLM output) to Change (internal model).

    NEW METHOD - Phase 1
    """
    file_type = self.detect_file_type(parsed.file_path)
    fingerprint = self.generate_fingerprint(
        parsed.file_path,
        parsed.start_line,
        parsed.end_line,
        parsed.new_content,
    )

    return Change(
        path=parsed.file_path,
        start_line=parsed.start_line,
        end_line=parsed.end_line,
        content=parsed.new_content,
        metadata={
            "url": comment.get("html_url", ""),
            "author": (comment.get("user") or {}).get("login", ""),
            "source": "llm",
            "option_label": None,  # TODO: Extract from comment if present
        },
        fingerprint=fingerprint,
        file_type=file_type,
        llm_confidence=parsed.confidence,
        llm_provider=self.config.get("llm_provider", "claude"),
        parsing_method="llm",
        change_rationale=parsed.rationale,
        risk_level=parsed.risk_level,
    )

def _parse_single_comment_with_regex(self, comment: dict[str, Any]) -> list[Change]:
    """Parse a single comment using regex (fallback).

    NEW METHOD - Phase 1
    Extracts existing _parse_comment_suggestions logic for single comment.
    """
    # ... implementation ...

```

#### Task 1.6: Add Error Handling (4 hours)

**Enhance error handling throughout:**

1. Network timeout handling
2. Rate limit handling
3. Invalid JSON response handling
4. Fallback trigger logic
5. Detailed error logging

#### Task 1.7: Write Tests (4 hours)

**Unit tests:**

```python
# tests/llm/test_parser.py

def test_parse_suggestion_block(mock_llm_provider):
    """Test parsing ```suggestion blocks."""
    parser = UniversalLLMParser(mock_llm_provider)
    comment = """
    Apply this change:

    ```suggestion

    def foo():
        return "bar"

```text
    """

    parsed = parser.parse_comment(comment, file_path="test.py")
    assert len(parsed) == 1
    assert parsed[0].new_content == 'def foo():\n    return "bar"'

def test_parse_diff_block(mock_llm_provider):
    """Test parsing diff blocks."""
    # ... test implementation ...

def test_parse_natural_language(mock_llm_provider):
    """Test parsing prose suggestions."""
    # ... test implementation ...

def test_confidence_threshold_filtering():
    """Test that low-confidence changes are filtered."""
    # ... test implementation ...

def test_fallback_on_llm_failure():
    """Test fallback to regex when LLM fails."""
    # ... test implementation ...

```

### 6.2 Deliverables

* [ ] Abstract parser interface complete
* [ ] Prompt templates designed and tested
* [ ] Claude API provider working
* [ ] LLM parser implemented
* [ ] Integration into resolver.py complete
* [ ] Error handling robust
* [ ] Fallback to regex works
* [ ] Unit tests pass (>85% coverage on new code)
* [ ] Integration test with real API passes (in CI)

### 6.3 Success Criteria

* ✅ Can parse ```suggestion blocks via LLM
* ✅ Can parse diff blocks (`@@ -1,3 +1,3 @@`)
* ✅ Can parse natural language suggestions
* ✅ Fallback works when LLM fails
* ✅ Test coverage > 85% for new code

### 6.4 Testing

```bash
# Unit tests (mocked LLM)
pytest tests/llm/test_parser.py -v

# Integration test (real API - requires ANTHROPIC_API_KEY)
pytest tests/llm/test_parser.py -v --integration

# Expected: 5 changes parsed (vs 1 with regex)

```

---

## 7. Phase 2: Multi-Provider Support (25-30 hours)

**Goal:** Add OpenAI, Claude CLI, Codex CLI, Ollama providers.

**GitHub Issue:** #27
**Milestone:** v2.0 - LLM-First Architecture
**Dependencies:** Phase 1 (#26)
**Estimated Effort:** 25-30 hours

### 7.1 Tasks

#### Task 2.1: Implement OpenAI Provider (6 hours)

**File:** `src/review_bot_automator/llm/providers/openai_api.py`

**Implementation:**

```python
"""OpenAI GPT API provider implementation."""

import logging
from typing import Any

import openai
from tenacity import retry, stop_after_attempt, wait_exponential

from review_bot_automator.llm.base import LLMProvider

logger = logging.getLogger(__name__)

class OpenAIProvider:
    """OpenAI GPT provider implementation.

    Supports GPT-5, GPT-5-Mini, GPT-5-Nano models.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5-mini",
        timeout: int = 60,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model identifier (gpt-5, gpt-5-mini, gpt-5-nano)
            timeout: Request timeout in seconds
        """
        self.client = openai.OpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.total_tokens_used = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate completion with structured output.

        Uses OpenAI's JSON mode for reliable structured output.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "system",
                    "content": "You are a code change extractor. Output only valid JSON."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=max_tokens,
                temperature=0.0,
                response_format={"type": "json_object"},  # Force JSON output
            )

            # Track usage
            usage = response.usage
            self.total_tokens_used += usage.prompt_tokens + usage.completion_tokens

            logger.debug(
                f"OpenAI API call: {usage.prompt_tokens} prompt + "
                f"{usage.completion_tokens} completion tokens"
            )

            return response.choices[0].message.content

        except openai.AuthenticationError as e:
            logger.error(f"OpenAI authentication failed: {e}")
            raise RuntimeError(f"OpenAI API authentication error: {e}") from e

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API error: {e}") from e

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback for newer models
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

```

#### Task 2.2: Implement Claude Code CLI Provider (7 hours)

**File:** `src/review_bot_automator/llm/providers/claude_cli.py`

**Implementation:**

```python
"""Claude Code CLI provider (headless mode)."""

import logging
import subprocess
import tempfile
from pathlib import Path

from review_bot_automator.llm.base import LLMProvider

logger = logging.getLogger(__name__)

class ClaudeCLIProvider:
    """Claude Code CLI provider.

    Uses Claude Code in headless mode (requires claude.ai subscription).
    Zero marginal cost per API call.
    """

    def __init__(self, executable: str = "claude", timeout: int = 120):
        """Initialize Claude CLI provider.

        Args:
            executable: Path to claude executable
            timeout: Command timeout in seconds
        """
        self.executable = executable
        self.timeout = timeout
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if Claude CLI is installed and authenticated."""
        try:
            result = subprocess.run(
                [self.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Claude CLI not working: {result.stderr}")

            logger.info(f"Claude CLI detected: {result.stdout.strip()}")

        except FileNotFoundError:
            raise RuntimeError(
                f"Claude CLI not found: {self.executable}\n"
                "Install from: https://claude.ai/download"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude CLI timeout - may not be authenticated")

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate via Claude CLI.

        Writes prompt to temp file, invokes CLI, returns output.
        """
        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.txt',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            # Call Claude CLI in headless mode
            result = subprocess.run(
                [
                    self.executable,
                    "ask",
                    "--file", prompt_file,
                    "--no-stream",  # Get full response at once
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr}")
                raise RuntimeError(f"Claude CLI error: {result.stderr}")

            logger.debug(f"Claude CLI response length: {len(result.stdout)} chars")
            return result.stdout.strip()

        finally:
            # Clean up temp file
            Path(prompt_file).unlink(missing_ok=True)

    def count_tokens(self, text: str) -> int:
        """Estimate tokens (Claude CLI doesn't expose token count)."""
        # Rough estimate: ~4 chars per token
        return len(text) // 4

```

#### Task 2.3: Implement Codex CLI Provider (6 hours)

**File:** `src/review_bot_automator/llm/providers/codex_cli.py`

(Similar structure to Claude CLI, adapted for Codex CLI)

#### Task 2.4: Implement Ollama Provider (6 hours)

**File:** `src/review_bot_automator/llm/providers/ollama.py`

**Implementation:**

```python
"""Local Ollama provider (zero cost, privacy-first)."""

import logging
from typing import Any

import httpx

from review_bot_automator.llm.base import LLMProvider

logger = logging.getLogger(__name__)

class OllamaProvider:
    """Local Ollama provider.

    Connects to local Ollama instance for zero-cost, offline inference.
    Supports models like qwen2.5-coder, deepseek-coder-v2, codellama.
    """

    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ):
        """Initialize Ollama provider.

        Args:
            model: Model name (e.g., "qwen2.5-coder:7b")
            base_url: Ollama API endpoint
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if Ollama is running and model is available."""
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()

            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]

            if self.model not in model_names:
                logger.warning(
                    f"Model {self.model} not found in Ollama. "
                    f"Available: {model_names}\n"
                    f"Run: ollama pull {self.model}"
                )
            else:
                logger.info(f"Ollama model available: {self.model}")

        except httpx.ConnectError:
            raise RuntimeError(
                f"Ollama not running at {self.base_url}\n"
                "Start with: ollama serve"
            )
        except Exception as e:
            raise RuntimeError(f"Ollama availability check failed: {e}")

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate via Ollama API."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.0,
                        }
                    }
                )
                response.raise_for_status()

                result = response.json()
                generated_text = result["response"]

                logger.debug(f"Ollama response length: {len(generated_text)} chars")
                return generated_text

        except httpx.TimeoutException:
            raise RuntimeError(f"Ollama request timeout after {self.timeout}s")
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama HTTP error: {e}")

    def count_tokens(self, text: str) -> int:
        """Estimate tokens (Ollama doesn't expose token count)."""
        # Rough estimate: ~4 chars per token
        return len(text) // 4

```

#### Task 2.5: Add Provider Factory (3 hours)

**File:** `src/review_bot_automator/llm/providers/__init__.py`

**Implementation:**

```python
"""Provider factory for creating LLM providers based on config."""

import logging
import os

from review_bot_automator.llm.base import LLMProvider
from review_bot_automator.llm.providers.anthropic_api import ClaudeAPIProvider
from review_bot_automator.llm.providers.openai_api import OpenAIProvider
from review_bot_automator.llm.providers.claude_cli import ClaudeCLIProvider
from review_bot_automator.llm.providers.codex_cli import CodexCLIProvider
from review_bot_automator.llm.providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)

def create_provider(config: dict) -> LLMProvider:
    """Factory to create LLM provider based on configuration.

    Args:
        config: Configuration dict with llm_provider, llm_model, etc.

    Returns:
        Initialized LLM provider instance

    Raises:
        ValueError: If provider is unknown or misconfigured
    """
    provider_name = config.get("llm_provider", "claude-cli").lower()
    model = config.get("llm_model")

    logger.info(f"Creating LLM provider: {provider_name} (model: {model})")

    if provider_name == "anthropic-api":
        api_key = config.get("llm_api_key") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API provider requires ANTHROPIC_API_KEY. "
                "Set via environment variable or config."
            )
        return ClaudeAPIProvider(
            api_key=api_key,
            model=model or "claude-sonnet-4-20250514",
        )

    elif provider_name in ("openai", "openai-api"):
        api_key = config.get("llm_api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI provider requires OPENAI_API_KEY. "
                "Set via environment variable or config."
            )
        return OpenAIProvider(
            api_key=api_key,
            model=model or "gpt-5-mini",
        )

    elif provider_name == "claude-cli":
        return ClaudeCLIProvider(
            executable=config.get("claude_cli_path", "claude"),
        )

    elif provider_name == "codex-cli":
        return CodexCLIProvider(
            executable=config.get("codex_cli_path", "codex"),
        )

    elif provider_name == "ollama":
        return OllamaProvider(
            model=model or "qwen2.5-coder:7b",
            base_url=config.get("ollama_base_url", "http://localhost:11434"),
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: {provider_name}. "
            f"Supported: anthropic-api, openai, claude-cli, codex-cli, ollama"
        )

```

#### Task 2.6: Update CLI (3 hours)

**Modify:** `src/review_bot_automator/cli/main.py`

```python
@click.option("--llm-provider",
              type=click.Choice([
                  "anthropic-api",
                  "openai",
                  "claude-cli",
                  "codex-cli",
                  "ollama"
              ]),
              default="claude-cli",
              help="LLM provider to use")

```

#### Task 2.7: Write Tests (4 hours)

**Test each provider:**

```python
# tests/llm/providers/test_anthropic_api.py
# tests/llm/providers/test_openai_api.py
# tests/llm/providers/test_claude_cli.py
# tests/llm/providers/test_codex_cli.py
# tests/llm/providers/test_ollama.py

@pytest.mark.integration
def test_anthropic_provider_real_api():
    """Test Anthropic provider with real API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    provider = ClaudeAPIProvider(api_key)
    response = provider.generate("Output JSON: [{\"test\": true}]", max_tokens=100)

    assert response
    assert isinstance(response, str)
    # Verify JSON parseable
    json.loads(response)

```

### 7.2 Deliverables

* [ ] 5 provider implementations complete
* [ ] Provider factory working
* [ ] CLI updated with provider selection
* [ ] Documentation for each provider
* [ ] Tests pass for all providers
* [ ] Integration tests with real APIs (optional, in CI)

### 7.3 Success Criteria

* ✅ All 5 providers can parse CodeRabbit comments
* ✅ Can switch providers via config/CLI
* ✅ Graceful failure if provider unavailable
* ✅ Test coverage > 85%
* ✅ Clear error messages for misconfiguration

### 7.4 Testing

```bash
# Test each provider (requires keys/installations)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...

pr-resolve analyze --pr 8 --llm --llm-provider anthropic-api
pr-resolve analyze --pr 8 --llm --llm-provider openai
pr-resolve analyze --pr 8 --llm --llm-provider claude-cli
pr-resolve analyze --pr 8 --llm --llm-provider codex-cli
pr-resolve analyze --pr 8 --llm --llm-provider ollama --llm-model qwen2.5-coder:7b

# All should parse 5/5 comments

```

---

## 8. Phase 3: CLI Integration Polish (15-20 hours)

**Goal:** Make CLI tools seamless with auto-detection and setup wizard.

**GitHub Issue:** #28
**Milestone:** v2.0 - LLM-First Architecture
**Dependencies:** Phase 2 (#27)
**Estimated Effort:**15-20 hours

### 8.1 Tasks

#### Task 3.1: Auto-Detection (5 hours)

* Detect installed CLI tools (claude, codex)
* Choose best default provider
* Warn if no providers available

#### Task 3.2: Setup Wizard (4 hours)

* `pr-resolve setup-llm` command
* Guide user through provider selection
* Test provider connection
* Save configuration

#### Task 3.3: Provider Testing Command (3 hours)

* `pr-resolve test-llm --provider <name>` command
* Test provider availability
* Simple parsing test
* Cost estimation

#### Task 3.4: Documentation (4 hours)

* Provider comparison matrix
* Setup guides per provider
* Troubleshooting guide
* Performance benchmarks

#### Task 3.5: Examples (4 hours)

* Example configs for each provider
* Example comments (all formats)
* Example outputs

### 8.2 Deliverables

* [ ] Auto-detection working
* [ ] Setup wizard functional
* [ ] Testing command works
* [ ] Comprehensive docs
* [ ] Examples for all providers

### 8.3 Success Criteria

* ✅ New users can set up in < 5 minutes
* ✅ Clear error messages
* ✅ Provider comparison helps choice

---

## 9. Phase 4: Local Model Support (15-20 hours)

**Goal:** Full offline, zero-cost operation with Ollama.

**GitHub Issue:** #29
**Milestone:** v2.0 - LLM-First Architecture
**Dependencies:** Phase 2 (#27)
**Estimated Effort:**15-20 hours

### 9.1 Tasks

#### Task 4.1: Ollama Integration Polish (5 hours)

* Test with multiple models
* Optimize prompts for smaller models
* Tune parameters

#### Task 4.2: Model Download Helper (4 hours)

* `pr-resolve llm download-model <name>` command
* Wraps `ollama pull`

#### Task 4.3: Prompt Optimization (4 hours)

* Shorter prompts for smaller models
* Few-shot examples
* Template variants per model family

#### Task 4.4: Performance Testing (3 hours)

* Benchmark accuracy per model
* Measure latency
* Compare quality vs API models

#### Task 4.5: Documentation (4 hours)

* Ollama setup guide
* Model recommendations
* Accuracy comparison
* Troubleshooting

### 9.2 Deliverables

* [ ] Ollama integration production-ready
* [ ] Model download helper
* [ ] Optimized prompts
* [ ] Performance benchmarks
* [ ] Documentation complete

### 9.3 Success Criteria

* ✅ Works offline with no API keys
* ✅ Accuracy ≥ 85% for common formats
* ✅ Latency < 10s per comment

---

## 10. Phase 5: Optimization & Production Readiness (25-30 hours)

**Goal:** Caching, cost tracking, performance tuning.

**GitHub Issue:** #30
**Milestone:** v2.1 - Optimization
**Dependencies:** Phases 3 & 4 (#28, #29)
**Estimated Effort:** 25-30 hours

### 10.1 Tasks

#### Task 5.1: Implement Response Caching (8 hours)

* Cache LLM responses by prompt hash
* 60%+ cache hit rate target
* LRU eviction policy

#### Task 5.2: Implement Cost Tracking (8 hours)

* Track tokens and costs per provider
* Cost per PR reporting
* Budget alerts

#### Task 5.3: Add Rate Limiting (4 hours)

* Respect API rate limits
* Token bucket algorithm

#### Task 5.4: Batch Processing (5 hours)

* Group multiple comments in one request
* Reduce API calls

#### Task 5.5: Performance Tuning (3 hours)

* Parallel LLM calls (where safe)
* Async/await optimization

#### Task 5.6: Monitoring & Metrics (2 hours)

* Log parsing success rate
* Log latency metrics
* Log cost per PR

### 10.2 Deliverables

* [ ] Response caching working
* [ ] Cost tracking implemented
* [ ] Rate limiting prevents errors
* [ ] Batch processing optimized
* [ ] Performance tuned
* [ ] Monitoring in place

### 10.3 Success Criteria

* ✅ Cache hit rate > 50%
* ✅ Cost visible to users
* ✅ No rate limit errors
* ✅ 2-3x faster for large PRs with batching

---

## 11. Phase 6: Documentation & Migration (15-20 hours)

**Goal:** Complete docs for users and developers.

**GitHub Issue:** #31
**Milestone:** v2.1 - Optimization
**Dependencies:** Phase 5 (#30)
**Estimated Effort:**15-20 hours

### 11.1 Tasks

#### Task 6.1: User Documentation (8 hours)

* `docs/llm-parsing.md`: Comprehensive guide
* `docs/llm-providers.md`: Provider comparison
* `docs/llm-configuration.md`: All config options
* `docs/llm-troubleshooting.md`: Common issues
* Update `README.md`

#### Task 6.2: Migration Guide (4 hours)

* `docs/migration/v1-to-v2.md`
* Regex → LLM transition
* Config changes
* Rollback instructions

#### Task 6.3: API Documentation (3 hours)

* Document `LLMParser` interface
* Document `LLMProvider` protocol
* Code examples

#### Task 6.4: Developer Guide (5 hours)

* Architecture diagrams
* Adding new providers
* Testing LLM code
* Debugging tips

### 11.2 Deliverables

* [ ] Complete user docs
* [ ] Migration guide
* [ ] API docs
* [ ] Developer guide
* [ ] Updated README

### 11.3 Success Criteria

* ✅ Users can migrate without support
* ✅ New contributors can add providers
* ✅ All config options documented

---

## 12. Risk Assessment & Mitigation

### 12.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
| ------ | ------------ | -------- | ------------ |
| **LLM accuracy lower than regex** | Medium | High | Confidence thresholds, validation layer, fallback to regex, A/B testing |
| **API costs too high** | Medium | Medium | Cost tracking, budgets, cache aggressively, local models default |
| **Latency unacceptable** | Low | Medium | Parallel requests, streaming, local models, timeout fallback |
| **Provider API outages** | Low | High | Multi-provider support, automatic failover, regex fallback, local models |
| **Security vulnerabilities** | Low | Critical | API key security, input sanitization, secret scanning in LLM responses, audit logging |

### 12.2 Project Risks

| Risk | Likelihood | Impact | Mitigation |
| ------ | ------------ | -------- | ------------ |
| **Scope creep** | High | High | Strict phase boundaries, MVP mindset, feature freeze during implementation |
| **Timeline underestimation** | Medium | Medium | 25% buffer in estimates, parallel work where possible, early validation |
| **Provider API changes** | Medium | High | Abstract provider interface, version pinning, multi-provider strategy |
| **Insufficient test coverage** | Medium | High | 90%+ target, extensive mocking, snapshot testing, fuzzing |

### 12.3 User Impact Risks

| Risk | Likelihood | Impact | Mitigation |
| ------ | ------------ | -------- | ------------ |
| **Users confused by options** | Medium | Medium | Smart defaults (Claude CLI), setup wizard, clear docs, provider comparison |
| **Breaking existing workflows** | Low | Critical | Feature flag OFF by default, 6-month migration period, rollback support |
| **Cost surprise** | Medium | High | Cost estimation upfront, budget warnings, cost transparency, free tier prominent |

---

## 13. Cost Analysis

### 13.1 Per-Comment Cost Breakdown

**Assumptions:**

* Average comment: 2,300 tokens (input)
* Average parsed output: 500 tokens
* Cache hit rate: 30% (conservative)

| Provider | Input Cost | Output Cost | Per Comment | Per 1K Comments | With 30% Cache |
| ---------- | ----------- | ------------- | ------------- | ----------------- | ---------------- |
| **Claude Sonnet 4.5 API** | $0.00690 | $0.0075 | $0.0144 | $14.40 | $10.08 |
| **Claude Haiku 4.5 API** | $0.00058 | $0.00063 | $0.00121 | $1.21 | $0.85 |
| **GPT-5-Mini API** | TBD | TBD | ~$0.002-0.005 | ~$2-5 | ~$1.40-3.50 |
| **Claude Code CLI** | $0 | $0 | $0 | $0 | $0 |
| **Codex CLI** | $0 | $0 | $0 | $0 | $0 |
| **Ollama (Local)** | $0 | $0 | $0 | $0 | $0 |

### 13.2 Monthly Cost Projections

| Team Size | PRs/Day | Comments/Day | Monthly (Haiku API) | Monthly (Sonnet API) | Monthly (CLI/Local) |
| ----------- | --------- | -------------- | --------------------- | ---------------------- | --------------------- |
| **Small (10 PRs)** | 10 | 200 | $5.10 | $60.48 | $0 |
| **Medium (50 PRs)** | 50 | 1,000 | $25.50 | $302.40 | $0 |
| **Large (200 PRs)** | 200 | 4,000 | $102.00 | $1,209.60 | $0 |
| **Enterprise (1K PRs)** | 1,000 | 20,000 | $510.00 | $6,048.00 | $0 |

**With Phase 5 Caching (50-90% additional reduction):**

* Small team: $2.55-5.10/month (Haiku)
* Medium team: $12.75-25.50/month (Haiku)
* Large team: $51-102/month (Haiku)

### 13.3 Cost Recommendations

**For Most Users:** Claude Code CLI or Codex CLI (zero cost, subscription-based)
**For API Users:** Claude Haiku 4.5 ($0.85-5.10/month for most teams)
**For Privacy:** Ollama (zero cost, fully local)

---

## 14. Success Metrics

### 14.1 Technical KPIs

**Parsing Accuracy:**

* Target: ≥ 90% for ```suggestion blocks
* Target: ≥ 85% for diff blocks
* Target: ≥ 80% for natural language
* Measure: Precision/recall vs hand-labeled test set (100 comments)

**Performance:**

* Target: < 5s latency per comment (with caching)
* Target: < 30s for 50-comment PR
* Target: Cache hit rate > 50% (after warm-up)
* Measure: Benchmark suite, production telemetry

**Coverage:**

* Target: 100% of CodeRabbit comment formats
* Target: 90%+ test coverage on LLM code
* Target: No regression in existing tests
* Measure: pytest + coverage.py

**Reliability:**

* Target: < 1% hard failures (with fallback)
* Target: 100% backward compatibility
* Target: Zero security vulnerabilities
* Measure: Production monitoring, security audits

### 14.2 User Metrics (6 months post-launch)

**Adoption:**

* Target: 20% of existing users enable LLM parsing
* Target: 50% of new users enable LLM
* Measure: Telemetry (opt-in)

**Satisfaction:**

* Target: ≥ 4.0/5.0 user satisfaction with LLM parsing
* Target: < 5% revert to regex-only mode
* Measure: User surveys, GitHub issues

**Cost:**

* Target: < $0.50 per PR average (API users)
* Target: 80% of users choose CLI/local (zero cost)
* Measure: Cost tracking logs

### 14.3 Business Metrics

**Community Growth:**

* Target: +50% GitHub stars (LLM feature attraction)
* Target: +30% contributors
* Target: Featured in AI/DevTools publications
* Measure: GitHub analytics, press monitoring

**Maintenance:**

* Target: < 10% of issues related to LLM
* Target: < 5% increase in support load
* Measure: Issue tracker, support tickets

---

## 15. Timeline & Milestones

### 15.1 Overall Timeline

```text
Week 1-2:   Phase 0 (Foundation) + Phase 1 (Basic LLM) start
Week 3-4:   Phase 1 complete + Phase 2 (Multi-Provider) start
Week 5-6:   Phase 2 complete + Phase 3 (CLI) + Phase 4 (Local) [parallel]
Week 7-8:   Phase 3 & 4 complete + Phase 5 (Optimization) start
Week 9-10:  Phase 5 complete + Phase 6 (Documentation)
Week 11-12: Phase 6 complete + Testing + Beta release

```

### 15.2 Milestones

**Milestone 1: LLM Proof of Concept** (After Phase 0 + Phase 1)

* Date: Week 3
* Goal: Parse one comment format with Claude API
* Success: Feature flag works, basic tests pass, 1 provider functional
* ETA: 55-70 hours

**Milestone 2: Multi-Provider MVP** (After Phase 2)

* Date: Week 5
* Goal: All 5 providers implemented
* Success: Users can choose provider, tests pass
* ETA: +25-30 hours = 80-100 hours total

**Milestone 3: Production Ready** (After Phases 3-5)

* Date: Week 9
* Goal: CLI polished, local models working, caching
* Success: Ready for beta testing
* ETA: +55-70 hours = 135-170 hours total

**Milestone 4: Full Release** (After Phase 6)

* Date: Week 11
* Goal: Documentation complete, migration guide ready
* Success: v2.0 release
* ETA: +15-20 hours = 150-190 hours total

### 15.3 Critical Path

```text
Phase 0 → Phase 1 → Phase 2 → Phase 5 → Phase 6
(Foundation → Basic LLM → Multi-Provider → Optimization → Docs)

```

**Parallelizable:**

* Phase 3 (CLI) and Phase 4 (Local) can run in parallel after Phase 2
* Documentation can start during Phase 5

---

## 16. Appendices

### 16.1 Test Corpus

**Create Test Set (100 comments):**

* 40x ```suggestion blocks (baseline, regex already works)
* 30x diff blocks (`@@ -1,3 +1,3 @@` format)
* 20x natural language ("change X to Y on line N")
* 10x multi-option suggestions

### Hand-Label Ground Truth

For each comment, manually extract:

* file_path
* start_line, end_line
* new_content
* change_type

**Evaluation Metrics:**

* **Precision:** % of extracted changes that are correct
* **Recall:** % of actual changes that were extracted
* **F1 Score:** Harmonic mean of precision and recall
* **Confidence Calibration:** Correlation between LLM confidence and actual accuracy

### 16.2 Glossary

* **Change:** A single suggested modification (line range + new content)
* **Conflict:** Two or more changes that overlap in line ranges
* **LLM Provider:** Service providing language model API (Claude, GPT, Ollama)
* **Parsing Method:** Technique to extract changes (regex or LLM)
* **Confidence Score:** LLM's self-assessed probability (0.0-1.0) that extraction is correct
* **Fallback:** Automatic reversion to regex parsing if LLM fails
* **Feature Flag:** Configuration toggle to enable/disable LLM parsing
* **Provider Factory:** Design pattern to select and instantiate LLM provider based on config

### 16.3 Related Documents

* [LLM Architecture Specification](./LLM_ARCHITECTURE.md) - Detailed technical architecture
* [Migration Guide](./MIGRATION_GUIDE.md) - v1.x → v2.0 migration path
* [Main Roadmap](./ROADMAP.md) - Overall project roadmap
* [Security Architecture](../security-architecture.md) - Security foundation (Phase 0)

---

**Document Maintained By:** VirtualAgentics Team
**Questions/Feedback:** Create GitHub issue or discussion
**Last Review Date:** 2025-11-06

---

*This roadmap represents a strategic transformation from a narrow conflict resolver to a universal AI-powered suggestion applier. Each phase builds incrementally on the last, maintaining backward compatibility while expanding capabilities 5x. The foundation is solid; the path is clear; the outcome will be transformative.*
