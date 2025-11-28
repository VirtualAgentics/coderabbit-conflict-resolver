# LLM Security Best Practices

## Executive Summary

This document outlines security considerations and best practices for the LLM-powered features in Review Bot Automator. The system uses external LLM APIs (Anthropic Claude, OpenAI, Ollama) to parse PR review comments and extract actionable code changes.

**Last Updated**: 2025-11-25
**Version**: 1.0

---

## Data Flow Security

### Overview

PR comment text flows through the following path:

```text
GitHub PR Comment → Secret Scanner → PARSE_COMMENT_PROMPT → LLM API → JSON Parser → ParsedChange Objects
```

### Critical Security Gates

1. **Secret Scanning (Pre-LLM)**
   * All comment bodies are scanned for secrets BEFORE being sent to external LLM APIs
   * Uses `SecretScanner.scan_content()` with 17 detection patterns
   * Raises `LLMSecretDetectedError` if secrets detected
   * Prevents accidental exfiltration of credentials to external services

2. **Input Validation**
   * Comment body length limits enforced
   * File path validation for extracted changes
   * Line number bounds checking

3. **Output Validation**
   * JSON response validation against expected schema
   * Confidence threshold filtering (default: 0.5)
   * Type checking on all ParsedChange fields

---

## Secret Protection

### What Gets Scanned

The `SecretScanner` detects:

* GitHub tokens (ghp_, gho_, ghs_, ghr_)
* AWS access keys (AKIA...)
* OpenAI API keys (sk-...)
* Private keys (BEGIN...PRIVATE KEY)
* JWT tokens
* Slack tokens
* Generic API keys and passwords

### Configuration

Secret scanning is enabled by default. To disable (NOT recommended for production):

```python
parser = UniversalLLMParser(provider, scan_for_secrets=False)
```

### Exception Handling

When secrets are detected:

1. `LLMSecretDetectedError` is raised with details
2. LLM API call is NOT made
3. Error includes secret types found (not actual secret values)
4. CLI displays security warning and aborts

---

## Prompt Injection Mitigation

### Risk Analysis

PR comments could contain malicious prompts attempting to:

* Extract system prompts or API keys
* Manipulate LLM responses
* Generate harmful code suggestions

### Mitigations

1. **Structured Output**
   * LLM is instructed to return JSON only
   * Responses are parsed with strict JSON validation
   * Non-JSON responses are rejected

2. **Schema Validation**
   * All parsed changes validated against `ParsedChange` dataclass
   * Required fields: file_path, start_line, end_line, original_code, suggested_code
   * Invalid structures ignored

3. **Confidence Filtering**
   * Low-confidence results (< threshold) are discarded
   * Helps filter out nonsensical or manipulated responses

4. **Logging**
   * All LLM interactions logged for audit
   * Response previews truncated to prevent log injection

---

## API Key Security

### Best Practices

1. **Environment Variables**
   * Store API keys in environment variables, not config files
   * Use `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`

2. **Key Rotation**
   * Rotate API keys periodically
   * Use separate keys for development/production

3. **Error Message Sanitization**
   * ResilientLLMProvider sanitizes exception messages
   * Secrets in error messages are redacted before propagation

### Configuration Example

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

---

## Cache Security

### Design

The prompt cache (`PromptCache`) stores:

* SHA-256 hash of prompts (NOT actual prompt text)
* Parsed response data
* Metadata (timestamp, token counts)

### File Permissions

* Cache directory: `0700` (owner only)
* Cache files: `0600` (owner read/write only)

### Why Hashing?

1. Secrets in prompts are never persisted to disk
2. Cache collisions are cryptographically unlikely
3. Cache can be safely inspected without exposing sensitive data

---

## Circuit Breaker Security

### Error Sanitization

The `ResilientLLMProvider` wraps LLM calls with:

* Exception message scanning for secrets
* Automatic redaction if secrets detected in errors
* Clean error propagation

### Example

```python
# If provider raises "Error with key: sk-abc123..."
# ResilientLLMProvider intercepts and raises:
# RuntimeError("Provider error (details redacted)")
```

---

## Metrics Export Security

### File Permissions

All exported metrics files have restricted permissions:

* JSON exports: `0600`
* CSV exports: `0600`

### What's Exported

Metrics include:

* Request counts and latencies
* Cost tracking data
* Error types (not full error messages)
* NO prompt content
* NO response content
* NO API keys

---

## Parallel Processing Security

### Thread Limits

`ParallelLLMParser` enforces:

* Maximum workers: 32 (hard limit)
* Rate limiting: configurable requests/second
* Thread-safe cost tracking

### Resource Protection

Hard limits prevent:

* Resource exhaustion attacks
* Accidental DoS of LLM APIs
* Thread pool explosion

---

## Cost Budgeting

### Configuration

```python
cost_tracker = CostTracker(budget=10.0, warning_threshold=0.8)
parser = UniversalLLMParser(provider, cost_tracker=cost_tracker)
```

### Behavior

1. Warning at 80% budget utilization (configurable)
2. Requests blocked at 100% budget
3. `LLMCostExceededError` raised when budget exceeded
4. Graceful fallback to regex parsing (if enabled)

---

## Configuration Recommendations

### Production

```python
parser = UniversalLLMParser(
    provider=provider,
    scan_for_secrets=True,       # Always enabled
    fallback_to_regex=True,      # Graceful degradation
    confidence_threshold=0.7,    # Higher quality
    cost_tracker=CostTracker(budget=50.0),
)
```

### Development/Testing

```python
parser = UniversalLLMParser(
    provider=provider,
    scan_for_secrets=True,       # Still enabled for safety
    fallback_to_regex=True,
    confidence_threshold=0.5,    # More permissive
)
```

### Local-Only LLM (Ollama)

```python
# Only disable secret scanning if LLM is truly local
parser = UniversalLLMParser(
    provider=OllamaProvider(model="codellama"),
    scan_for_secrets=False,      # Safe for local-only
)
```

---

## Incident Response

### If Secrets Are Detected

1. Review the PR comment for sensitive data
2. If legitimate secrets were posted:
   * Rotate the exposed credentials immediately
   * Edit/delete the PR comment
   * Review access logs for unauthorized use
3. If false positive:
   * Consider adding to allowed patterns (with caution)
   * Report to maintainers for pattern tuning

### If Cost Budget Is Exceeded

1. Review recent LLM usage patterns
2. Check for unusual comment volumes
3. Increase budget or reduce per-request costs
4. Consider caching configuration

### If LLM Parsing Fails

1. Check provider API status
2. Review circuit breaker state
3. Verify API key validity
4. Check rate limit status
5. Regex fallback should handle gracefully

---

## Audit Logging

### What's Logged

* LLM request initiation (provider, model)
* Request completion (success/failure, latency)
* Secret detection events (types, not values)
* Budget warnings and exceeded events
* Circuit breaker state changes

### Log Levels

* `INFO`: Request completions, parsing results
* `WARNING`: Budget warnings, circuit breaker trips
* `ERROR`: Secret detection, parsing failures, API errors

---

## Related Documentation

* [Threat Model](threat-model.md) - Full threat analysis
* [Security Testing](security-testing.md) - Test coverage details
* [Incident Response](incident-response.md) - Response procedures
