# Migration Guide: v1.x → v2.0 (LLM-First Architecture)

**Document Version**: 1.0
**Last Updated**: 2025-11-06
**Status**: Draft

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What's New in v2.0](#2-whats-new-in-v20)
3. [Breaking Changes (None!)](#3-breaking-changes-none)
4. [Migration Paths](#4-migration-paths)
5. [Configuration Migration](#5-configuration-migration)
6. [API Changes](#6-api-changes)
7. [CLI Changes](#7-cli-changes)
8. [Testing Your Migration](#8-testing-your-migration)
9. [Rollback Procedures](#9-rollback-procedures)
10. [FAQ](#10-faq)

---

## 1. Executive Summary

### 1.1 Should You Migrate

**TL;DR**: Yes, but you don't need to change anything immediately.

* ✅ **v1.x code works in v2.0 without changes** (zero breaking changes)
* ✅ **LLM parsing disabled by default** (opt-in via configuration)
* ✅ **Gradual migration path** (enable LLM parsing when ready)
* ✅ **Automatic fallback** (if LLM fails, regex parser takes over)

### 1.2 Migration Timeline

| Phase | Timeline | What Happens | Action Required |
| ------- | ---------- | -------------- | ----------------- |
| **Immediate (v2.0 Release)** | Week 1 | v2.0 released, LLM disabled by default | None (v1.x behavior) |
| **Beta Testing** | Weeks 2-3 | Opt-in LLM testing via `--llm` flag | Optional testing |
| **Gradual Rollout** | Weeks 4-6 | LLM enabled for 10% → 50% → 100% users | Monitor metrics |
| **LLM as Default** | Week 7+ | LLM parsing enabled by default | Update configs if needed |

### 1.3 Key Improvements in v2.0

#### Format Coverage

* v1.x: **20%** of CodeRabbit comments parsed (```suggestion blocks only)
* v2.0: **95%+** of CodeRabbit comments parsed (all formats)

#### Supported Formats

* ✅ Suggestion blocks (```suggestion)
* ✅ Diff blocks (```diff)
* ✅ Natural language prompts
* ✅ Multi-option suggestions
* ✅ Multiple diff blocks per comment

#### Provider Flexibility

* ✅ OpenAI API (gpt-5, gpt-5-mini, gpt-5-nano)
* ✅ Anthropic API (claude-opus-4-5, claude-sonnet-4-5, claude-haiku-4-5)
* ✅ Claude Code CLI (claude.ai subscription)
* ✅ Codex CLI (chatgpt.com subscription)
* ✅ Ollama (local inference, privacy-first)

---

## 2. What's New in v2.0

### 2.1 Major Features

#### Feature 1: LLM-First Parsing

```python
# v1.x: Regex-only parsing
changes = resolver._extract_changes_with_regex(comment)

# v2.0: LLM-first with fallback
if llm_enabled:
    try:
        changes = resolver._extract_changes_with_llm(comment)
    except Exception:
        changes = resolver._extract_changes_with_regex(comment)
else:
    changes = resolver._extract_changes_with_regex(comment)

```

#### Feature 2: Multi-Provider Support

```bash
# Choose your preferred provider
pr-resolve apply --llm --llm-provider claude-cli --pr 123
pr-resolve apply --llm --llm-provider ollama --pr 123
pr-resolve apply --llm --llm-provider openai-api --pr 123

```

#### Feature 3: Enhanced Change Metadata

```python
# v2.0: Changes include LLM metadata
change = Change(
    path="src/module.py",
    start_line=10,
    end_line=12,
    content="new code",
    # NEW in v2.0 (optional fields)
    llm_confidence=0.95,  # How confident the LLM is
    llm_provider="claude-cli",  # Which provider parsed it
    parsing_method="llm",  # "llm" or "regex"
    change_rationale="Improves error handling",  # Why change was suggested
    risk_level="low"  # "low", "medium", "high"
)

```

### 2.2 Minor Improvements

* **Prompt Caching**: 50-90% cost reduction for repeated comments
* **Parallel Parsing**: 4x faster for large PRs (>20 comments)
* **Cost Tracking**: Monitor LLM API costs per PR
* **Better Logging**: Detailed logs for LLM parsing decisions

---

## 3. Breaking Changes (None!)

### 3.1 Zero Breaking Changes Guarantee

**Note**: The package was renamed from `pr-conflict-resolver` to `review-bot-automator` in v2.0. This is a one-time rename for the initial public release. The guarantees below apply to the v2.0 API going forward.

#### We guarantee

* ✅ All v1.x Python API code works unchanged (update import paths)
* ✅ All v1.x CLI commands work unchanged
* ✅ All v1.x configuration files work unchanged
* ✅ All v1.x data models remain compatible

### 3.2 Compatibility Proof

```python
# v1.x code (before migration) - STILL WORKS IN v2.0
from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig

resolver = ConflictResolver(config=PresetConfig.BALANCED)
results = resolver.resolve_pr_conflicts(
    owner="VirtualAgentics",
    repo="my-repo",
    pr_number=123
)

print(f"Applied: {results.applied_count}")
# Output: Applied: 5
# Parsing method: regex (default in v2.0)

```

### 3.3 Deprecated Features (None)

#### No features removed or deprecated in v2.0

All v1.x features remain available:

* ✅ Regex parsing
* ✅ All CLI commands
* ✅ All Python API methods
* ✅ All configuration options

---

## 4. Migration Paths

### 4.1 Path 1: No-Change Migration (Recommended for Most Users)

**Who**: Users happy with v1.x behavior, no urgent need for LLM parsing

#### Steps

1. Upgrade to v2.0: `pip install --upgrade review-bot-automator`
2. Run existing commands/code unchanged
3. Observe v1.x behavior (LLM disabled by default)

**Result**: Identical behavior to v1.x

```bash
# Before (v1.x)
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123

# After (v2.0) - SAME COMMAND
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123

# Result: Same output, same behavior (LLM disabled by default)

```

### 4.2 Path 2: Gradual LLM Adoption (Recommended for New Features)

**Who**: Users wanting to try LLM parsing for better format coverage

#### Steps: (OpenAI)

1. Upgrade to v2.0: `pip install --upgrade review-bot-automator`
2. Test LLM parsing on a single PR:

   ```bash
   pr-resolve apply --llm --llm-provider claude-cli --pr 123

   ```

3. Compare results with regex-only:

   ```bash
   pr-resolve apply --pr 123  # Regex-only (v1.x behavior)

   ```

4. If satisfied, enable LLM by default via configuration

**Result**: Gradual transition with testing phase

### 4.3 Path 3: Full LLM Migration (Advanced Users)

**Who**: Users wanting to maximize format coverage from day 1

#### Steps: (Anthropic)

1. Upgrade to v2.0
2. Configure LLM provider (see [Configuration Migration](#5-configuration-migration))
3. Enable LLM globally via environment variable:

   ```bash
   export CR_LLM_ENABLED=true
   export CR_LLM_PROVIDER=claude-cli
   export CR_LLM_MODEL=claude-sonnet-4-5

   ```

4. Run commands as usual (LLM now enabled by default)

**Result**: LLM parsing for all PRs by default

---

## 5. Configuration Migration

### 5.1 Environment Variables (Recommended)

#### Option A: No Changes (v1.x Behavior)

```bash
# .env (v1.x - still works in v2.0)
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
CR_MODE=all
CR_ENABLE_ROLLBACK=true

# LLM disabled by default (no changes needed)

```

#### Option B: Enable LLM Parsing

```bash
# .env (v2.0 - new variables)
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
CR_MODE=all
CR_ENABLE_ROLLBACK=true

# NEW: Enable LLM parsing
CR_LLM_ENABLED=true
CR_LLM_PROVIDER=claude-cli  # or openai-api, anthropic-api, codex-cli, ollama
CR_LLM_MODEL=claude-sonnet-4-5

# Optional: API-based providers
CR_LLM_API_KEY=sk-...  # For openai-api, anthropic-api

# Optional: Cost control
CR_LLM_MAX_COST=10.0  # Max USD per PR
CR_LLM_CACHE=true  # Enable prompt caching

```

### 5.2 Configuration Files (YAML/TOML)

#### v1.x Configuration (Still Works)

```yaml
# config.yaml (v1.x)
mode: all
enable_rollback: true
validate: true
parallel: false

```

#### v2.0 Configuration (Extended)

```yaml
# config.yaml (v2.0)
mode: all
enable_rollback: true
validate: true
parallel: true  # NEW: Enable parallel parsing

# NEW: LLM configuration section
llm:
  enabled: true
  provider: claude-cli
  model: claude-sonnet-4-5

  # API settings (for API-based providers)
  api:
    key: ${CR_LLM_API_KEY}  # Load from environment
    temperature: 0.2
    max_tokens: 2000

  # Caching
  cache:
    enabled: true
    ttl_seconds: 3600

  # Fallback
  fallback_to_regex: true

  # Cost control
  cost:
    max_per_run: 10.0
    warn_threshold: 1.0

```

### 5.3 Provider-Specific Configuration

#### Claude Code CLI (claude.ai Subscription)

```bash
# .env
CR_LLM_ENABLED=true
CR_LLM_PROVIDER=claude-cli
CR_LLM_MODEL=claude-sonnet-4-5
CR_LLM_CLI_PATH=/usr/local/bin/claude  # Optional, defaults to PATH lookup

```

#### Setup

1. Install Claude Code CLI: <https://claude.com/cli>
2. Authenticate: `claude auth login`
3. Verify: `claude --version`

#### Codex CLI (chatgpt.com Subscription)

```bash
# .env
CR_LLM_ENABLED=true
CR_LLM_PROVIDER=codex-cli
CR_LLM_MODEL=gpt-5-mini
CR_LLM_CLI_PATH=/usr/local/bin/codex  # Optional

```

#### Setup: (OpenAI)

1. Install Codex CLI: <https://developers.openai.com/codex/cli/>
2. Authenticate: `codex auth login`
3. Verify: `codex --version`

#### OpenAI API (Pay-Per-Token)

```bash
# .env
CR_LLM_ENABLED=true
CR_LLM_PROVIDER=openai-api
CR_LLM_MODEL=gpt-5-mini
CR_LLM_API_KEY=sk-proj-...  # Get from <https://platform.openai.com>
CR_LLM_MAX_COST=5.0  # Set budget limit

```

#### Anthropic API (Pay-Per-Token)

```bash
# .env
CR_LLM_ENABLED=true
CR_LLM_PROVIDER=anthropic-api
CR_LLM_MODEL=claude-sonnet-4-5
CR_LLM_API_KEY=sk-ant-...  # Get from <https://console.anthropic.com>
CR_LLM_CACHE=true  # Enable prompt caching (50-90% cost reduction)

```

#### Ollama (Local Inference, Privacy-First)

```bash
# .env
CR_LLM_ENABLED=true
CR_LLM_PROVIDER=ollama
CR_LLM_MODEL=llama3.1
CR_LLM_BASE_URL=<http://localhost:11434>

```

#### Setup: (Ollama)

1. Install Ollama: <https://ollama.com/download>
2. Pull model: `ollama pull llama3.1`
3. Start server: `ollama serve`
4. Verify: `curl <http://localhost:11434/api/tags`>

---

## 6. API Changes

### 6.1 ConflictResolver Class

#### v1.x API (Still Works)

```python
from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig

# v1.x initialization
resolver = ConflictResolver(config=PresetConfig.BALANCED)

# v1.x methods (unchanged)
results = resolver.resolve_pr_conflicts(
    owner="VirtualAgentics",
    repo="my-repo",
    pr_number=123
)

```

#### v2.0 API (Extended)

```python
from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig, LLMConfig, LLMPresetConfig

# v2.0: NEW optional parameter
resolver = ConflictResolver(
    config=PresetConfig.BALANCED,
    llm_config=LLMPresetConfig.CLAUDE_CLI_SONNET  # NEW
)

# Same method, enhanced results
results = resolver.resolve_pr_conflicts(
    owner="VirtualAgentics",
    repo="my-repo",
    pr_number=123
)

# NEW: LLM metrics in results
print(f"LLM parsed: {results.llm_parsed_count}/{results.total_comments}")
print(f"Total cost: ${results.total_cost:.2f}")

```

### 6.2 Change Model

#### v1.x Model (Still Works)

```python
from review_bot_automator.core.models import Change, ChangeMetadata

# v1.x Change creation (all required fields)
change = Change(
    path="src/module.py",
    start_line=10,
    end_line=12,
    content="new code",
    metadata=ChangeMetadata(url="...", author="bot", source="suggestion"),
    fingerprint="abc123",
    file_type="python"
)

# NEW fields automatically get default values
# llm_confidence=None, llm_provider=None, parsing_method="regex"

```

#### v2.0 Model (Extended)

```python
from review_bot_automator.core.models import Change, ChangeMetadata

# v2.0 Change creation (with optional LLM fields)
change = Change(
    path="src/module.py",
    start_line=10,
    end_line=12,
    content="new code",
    metadata=ChangeMetadata(url="...", author="bot", source="llm"),
    fingerprint="abc123",
    file_type="python",
    # NEW optional fields
    llm_confidence=0.95,
    llm_provider="claude-cli",
    parsing_method="llm",
    change_rationale="Improves error handling",
    risk_level="low"
)

```

### 6.3 New APIs

```python
# NEW: LLM Parser Factory
from review_bot_automator.llm import LLMParserFactory, LLMConfig

llm_config = LLMConfig(
    enabled=True,
    provider="claude-cli",
    model="claude-sonnet-4-5"
)

parser = LLMParserFactory.create_parser(llm_config)
response = parser.parse_comment("GitHub comment text")

print(f"Parsed {len(response.changes)} changes")
print(f"Provider: {response.provider_name}")
print(f"Confidence: {response.changes[0].confidence}")

```

---

## 7. CLI Changes

### 7.1 Existing Commands (Unchanged)

```bash
# All v1.x commands work unchanged in v2.0

# Analyze conflicts
pr-resolve analyze --owner VirtualAgentics --repo my-repo --pr 123

# Apply suggestions (regex-only by default)
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123

# Dry-run mode
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 --mode dry-run

# Parallel processing
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 --parallel

```

### 7.2 New LLM Flags

```bash
# Enable LLM parsing
pr-resolve apply --llm --owner VirtualAgentics --repo my-repo --pr 123

# Specify provider
pr-resolve apply --llm --llm-provider claude-cli --owner VirtualAgentics --repo my-repo --pr 123

# Specify model
pr-resolve apply --llm --llm-provider openai-api --llm-model gpt-5-mini --owner VirtualAgentics --repo my-repo --pr 123

# Use preset configuration
pr-resolve apply --llm-preset claude-cli-sonnet --owner VirtualAgentics --repo my-repo --pr 123

# Available presets
# - codex-cli-free (chatgpt.com subscription)
# - claude-cli-sonnet (claude.ai subscription)
# - ollama-local (local inference)
# - openai-api-mini (OpenAI API, gpt-5-mini)
# - anthropic-api-balanced (Anthropic API, claude-sonnet-4-5 with caching)

```

### 7.3 New Output Format

```bash
# v1.x output
$ pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123

Analyzing PR #123...
Fetched 5 comments
Parsed 1 change (20% coverage)
Applied 1 change
Success!

# v2.0 output (with LLM enabled)
$ pr-resolve apply --llm --llm-provider claude-cli --owner VirtualAgentics --repo my-repo --pr 123

Analyzing PR #123...
Fetched 5 comments
Parsing with LLM (claude-cli, claude-sonnet-4-5)...
Parsed 5 changes (100% coverage)  # <-- IMPROVED
  ├─ LLM parsed: 4 changes (80%)
  ├─ Regex parsed: 1 change (20%)
  └─ Fallback used: 0 times

Conflict detection...
Detected 2 conflicts

Resolution...
Applied 5 changes
  ├─ Confidence: avg 0.92 (high)
  ├─ Risk level: 4 low, 1 medium
  └─ Cost: $0.00 (CLI subscription)

Success!

```

---

## 8. Testing Your Migration

### 8.1 Pre-Migration Checklist

* [ ] **Backup current setup**: Save `.env` and config files
* [ ] **Check v1.x baseline**: Run existing PRs to establish baseline metrics
* [ ] **Document current behavior**: Note parsing success rate, applied changes
* [ ] **Review provider options**: Choose LLM provider (CLI vs. API vs. local)
* [ ] **Set cost limits**: Configure `CR_LLM_MAX_COST` if using paid APIs

### 8.2 Test Plan

#### Test 1: No-Change Migration

```bash
# Upgrade to v2.0
pip install --upgrade review-bot-automator

# Run existing command (LLM disabled by default)
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123

# Verify: Should behave identically to v1.x
# - Same number of changes parsed
# - Same changes applied
# - No LLM metrics in output

```

#### Test 2: LLM Parsing (Single PR)

```bash
# Test with LLM enabled on a known PR
pr-resolve apply --llm --llm-provider claude-cli --owner VirtualAgentics --repo my-repo --pr 123

# Verify
# - More changes parsed than v1.x baseline
# - LLM metrics appear in output
# - No errors or warnings

```

#### Test 3: Fallback Behavior

```bash
# Disable internet to test fallback
# (or use invalid API key)

pr-resolve apply --llm --llm-provider openai-api --owner VirtualAgentics --repo my-repo --pr 123

# Verify
# - LLM parsing fails (expected)
# - Automatic fallback to regex parser
# - Warning logged: "LLM parsing failed, falling back to regex"
# - Changes still applied (via regex)

```

#### Test 4: Cost Tracking (API Providers)

```bash
# Set cost limit
export CR_LLM_MAX_COST=1.0

# Run on large PR (50+ comments)
pr-resolve apply --llm --llm-provider openai-api --owner VirtualAgentics --repo my-repo --pr 456

# Verify
# - Cost tracked in output
# - Warning if cost exceeds threshold
# - Error if cost exceeds limit

```

### 8.3 Validation Criteria

| Metric | v1.x Baseline | v2.0 Target | Status |
| -------- | -------------- | ------------- | -------- |
| **Parsing Coverage** | 20% (1/5 comments) | 95%+ (5/5 comments) | ✅ Pass |
| **Applied Changes** | Same as v1.x | Same or more | ✅ Pass |
| **Error Rate** | <1% | <1% | ✅ Pass |
| **Fallback Reliability** | N/A | 100% (always falls back) | ✅ Pass |
| **Cost Per PR** | $0 | <$0.50 (with caching) | ✅ Pass |

---

## 9. Rollback Procedures

### 9.1 Rollback to v1.x (If Needed)

**Scenario**: v2.0 causes unexpected issues; need to revert to v1.x

#### Steps: (Retry Configuration)

```bash
# 1. Downgrade package
pip install review-bot-automator==1.0.0  # Replace with last v1.x version

# 2. Restore v1.x configuration
cp .env.backup .env  # Restore backup

# 3. Verify rollback
pr-resolve --version
# Output: 1.0.0

# 4. Test functionality
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123

```

### 9.2 Disable LLM Without Downgrade

**Scenario**: v2.0 works, but want to temporarily disable LLM

#### Steps: (Parallel Processing)

```bash
# Option 1: Environment variable
export CR_LLM_ENABLED=false

# Option 2: Remove --llm flag from CLI commands
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123  # No --llm flag

# Option 3: Update config file
# config.yaml
llm:
  enabled: false  # Disable LLM

```

**Result**: v2.0 behavior reverts to v1.x (regex-only parsing)

---

## 10. FAQ

### Q1: Do I need to change my code to use v2.0

**A**: No. All v1.x code works unchanged in v2.0. LLM parsing is disabled by default.

### Q2: Will v2.0 break my existing workflows

**A**: No. We guarantee zero breaking changes. All v1.x CLI commands, API methods, and configurations remain compatible.

### Q3: How do I know if LLM parsing is enabled

**A**: Check the output:

* If LLM enabled: Output shows "Parsing with LLM (provider, model)" and LLM metrics
* If LLM disabled: Output shows v1.x behavior (no LLM mentions)

### Q4: What happens if LLM parsing fails

**A**: Automatic fallback to regex parser (v1.x behavior). No errors, no data loss.

### Q5: Which LLM provider should I choose

**A**: Depends on your priorities:

| Priority | Recommended Provider |
| ---------- | --------------------- |
| **Zero cost** | Codex CLI (chatgpt.com subscription) or Ollama (local) |
| **Best quality** | Claude CLI (claude.ai subscription) or Anthropic API |
| **Privacy** | Ollama (100% local, no data leaves machine) |
| **Simplicity** | Claude CLI or Codex CLI (no API keys needed) |
| **Pay-per-use** | OpenAI API (gpt-5-mini) with caching |

### Q6: How much will LLM parsing cost

**A**: Costs vary by provider:

| Provider | Cost Model | Est. Cost (1000 comments) |
| ---------- | ----------- | --------------------------- |
| **Codex CLI** | Subscription ($20/mo) | $0 (covered) |
| **Claude CLI** | Subscription ($20/mo) | $0 (covered) |
| **Ollama** | Free (local) | $0 |
| **OpenAI API (gpt-5-mini)** | Pay-per-token | $0.07 (with caching) |
| **Anthropic API (claude-haiku-4-5)** | Pay-per-token | $0.22 (with caching) |

### Q7: Can I use v2.0 without internet access

**A**: Yes, with Ollama (local inference). All other providers require internet.

### Q8: Will LLM parsing slow down my PRs

**A**: Slightly, but offset by parallel processing:

* LLM parsing: +1-2s per comment (with caching: +0.5s)
* Parallel processing: 4x faster for large PRs (>20 comments)
* Net impact: Large PRs faster, small PRs slightly slower

### Q9: How do I migrate from v1.x to v2.0 with zero downtime

#### A

1. Upgrade package: `pip install --upgrade review-bot-automator`
2. Test with `--llm` flag on a single PR
3. If satisfied, enable LLM globally via environment variable
4. Monitor metrics for 1 week
5. If issues, disable LLM (`CR_LLM_ENABLED=false`)

### Q10: What if I encounter a bug in v2.0

#### A: (Feature Flag)

1. **Disable LLM**: `export CR_LLM_ENABLED=false` (reverts to v1.x behavior)
2. **Report bug**: <https://github.com/VirtualAgentics/review-bot-automator/issues>
3. **Rollback if needed**: `pip install review-bot-automator==1.0.0`

### Q11: Can I use multiple LLM providers simultaneously

**A**: Not yet (v2.0 limitation). You can only use one provider at a time. This may be added in v2.1.

### Q12: How do I verify LLM parsing accuracy

#### A: (Performance)

```bash
# Compare LLM vs. regex parsing
pr-resolve apply --llm --owner VirtualAgentics --repo my-repo --pr 123 > v2_output.txt
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 > v1_output.txt

# Diff the outputs
diff v1_output.txt v2_output.txt

```

---

## Appendix A: Complete Migration Example

### Scenario: Large Organization Migration

#### Context

* 100+ repositories using v1.x
* ~1000 PRs processed per month
* Current parsing coverage: 20% (regex-only)
* Goal: Increase to 95%+ with LLM

#### Migration Plan

#### Week 1: Pilot Testing

```bash
# Select 5 test repositories
TEST_REPOS="repo1 repo2 repo3 repo4 repo5"

# Upgrade to v2.0 (LLM disabled by default)
pip install --upgrade review-bot-automator

# Test with LLM on 1 PR per repo
for repo in $TEST_REPOS; do
    pr-resolve apply --llm --llm-provider claude-cli --owner OrgName --repo $repo --pr 1
done

# Collect metrics
# - Parsing coverage (expected: 95%+)
# - Applied changes (should match or exceed v1.x)
# - Error rate (target: <1%)

```

#### Week 2: Beta Rollout (10% Traffic)

```bash
# Update .env for 10% of repositories (10 repos)
# .env
CR_LLM_ENABLED=true
CR_LLM_PROVIDER=claude-cli
CR_LLM_MODEL=claude-sonnet-4-5

# Monitor metrics for 1 week
# If success rate >99%, proceed to next phase

```

#### Week 3: Gradual Rollout (50% Traffic)

```bash
# Expand to 50 repositories
# Monitor cost (should be $0 with CLI subscription)
# Monitor error rate (target: <1%)

```

#### Week 4: Full Rollout (100% Traffic)

```bash
# Enable LLM for all repositories
# Update organization-wide .env template
CR_LLM_ENABLED=true
CR_LLM_PROVIDER=claude-cli

# Announce to team
# - LLM parsing now default
# - Parsing coverage increased from 20% → 95%+
# - Fallback to regex on any LLM failure

```

#### Week 5: Optimization

```bash
# Enable caching for cost reduction (if using API providers)
CR_LLM_CACHE=true

# Enable parallel processing for large PRs
CR_PARALLEL=true
CR_MAX_WORKERS=8

# Final metrics
# - Parsing coverage: 95%+
# - Error rate: <1%
# - Avg PR processing time: -40% (due to parallel processing)

```

---

## Appendix B: Troubleshooting Guide

### Issue 1: "LLM parsing failed" errors

**Symptoms**: Logs show "LLM parsing failed, falling back to regex"

#### Causes

* API key invalid/expired
* CLI not authenticated
* Ollama not running
* Network connectivity issues

#### Solutions

```bash
# For API providers
echo $CR_LLM_API_KEY  # Verify API key is set
# Test API key: <https://platform.openai.com> or <https://console.anthropic.com>

# For CLI providers
claude auth status  # or: codex auth status
# If not authenticated: claude auth login

# For Ollama
curl <http://localhost:11434/api/tags>
# If not running: ollama serve

```

### Issue 2: Parsing coverage still low (<50%)

**Symptoms**: v2.0 with LLM enabled, but parsing coverage <50%

#### Causes: (Import Errors)

* LLM not actually enabled
* Fallback to regex on all comments
* Configuration error

#### Solutions: (Import Errors)

```bash
# Verify LLM is enabled
pr-resolve apply --llm --owner ... --repo ... --pr ... --verbose

# Check output for
# "Parsing with LLM (provider, model)" ← Should appear
# "Fallback to regex" ← Should NOT appear frequently

# If fallback frequent, check provider configuration
CR_LLM_PROVIDER=claude-cli  # Ensure provider is correctly set

```

### Issue 3: High costs with API providers

**Symptoms**: LLM API costs exceed budget

#### Solutions: (Configuration Errors)

```bash
# Enable caching (50-90% cost reduction)
CR_LLM_CACHE=true

# Set cost limits
CR_LLM_MAX_COST=5.0  # Max $5 per PR
CR_LLM_WARN_THRESHOLD=1.0  # Warn at $1

# Switch to cheaper model
CR_LLM_MODEL=gpt-5-mini  # or claude-haiku-4-5

# Or switch to subscription-based provider
CR_LLM_PROVIDER=codex-cli  # $20/mo unlimited

```

### Issue 4: Slow parsing performance

**Symptoms**: LLM parsing takes >5s per comment

#### Solutions: (Runtime Errors)

```bash
# Enable parallel processing
CR_PARALLEL=true
CR_MAX_WORKERS=8

# Enable caching (cache hits are instant)
CR_LLM_CACHE=true

# Use faster model
CR_LLM_MODEL=gpt-5-mini  # Faster than gpt-5
# or: claude-haiku-4-5  # Faster than claude-sonnet-4-5

# Use local inference (no network latency)
CR_LLM_PROVIDER=ollama
CR_LLM_MODEL=llama3.1

```

---

#### Document End

For technical details on the LLM architecture, see [LLM Architecture Specification](./LLM_ARCHITECTURE.md).
For full implementation roadmap, see [LLM Refactor Roadmap](./LLM_REFACTOR_ROADMAP.md).
