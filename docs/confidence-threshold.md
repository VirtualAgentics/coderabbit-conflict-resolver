# Confidence Threshold Guide

The confidence threshold determines when to accept LLM-parsed changes versus falling back to regex parsing or rejecting the change entirely.

## Overview

When the LLM parses a CodeRabbit comment, it returns a confidence score (0.0-1.0) indicating how certain it is about the extracted changes. The confidence threshold filters out low-quality parses.

```text
Confidence Score:  0.0 ───────────────────────────────────────── 1.0
                    │              │                              │
                    │     REJECT   │      ACCEPT                  │
                    │  (fallback)  │   (use LLM result)           │
                    │              │                              │
                    └──────────────┴──────────────────────────────┘
                              threshold (default: 0.5)
```

## Configuration

### CLI Option

```bash
pr-resolve apply 123 --llm-enabled --llm-confidence-threshold 0.7
```

### Environment Variable

```bash
export CR_LLM_CONFIDENCE_THRESHOLD=0.7
```

### Config File (YAML)

```yaml
llm:
  confidence_threshold: 0.7
```

### Config File (TOML)

```toml
[llm]
confidence_threshold = 0.7
```

## How Confidence is Calculated

The LLM assigns confidence based on:

1. **Comment structure clarity**: Well-formatted suggestions score higher
2. **Code block presence**: Explicit code blocks increase confidence
3. **File path clarity**: Clear file references improve confidence
4. **Change type recognition**: Standard patterns (add, replace, delete) score higher

### Example Scores

| Comment Type | Typical Confidence |
|--------------|-------------------|
| Clear code suggestion with file path | 0.9-1.0 |
| Code block without explicit file | 0.7-0.85 |
| Inline suggestion | 0.5-0.7 |
| Ambiguous or complex comment | 0.3-0.5 |
| Unrelated or non-actionable | 0.0-0.3 |

## Threshold Recommendations

### Low Threshold (0.3-0.5)

**Use when:**

* You want maximum coverage
* Manual review will catch errors
* Comments are typically well-formatted

```yaml
llm:
  confidence_threshold: 0.3
  fallback_to_regex: true  # Let regex handle low-confidence
```

**Trade-off**: More changes applied, but some may be incorrect

### Default Threshold (0.5)

**Use when:**

* Balanced accuracy and coverage
* Standard CodeRabbit comment formats
* Automated pipelines with some oversight

```yaml
llm:
  confidence_threshold: 0.5
```

**Trade-off**: Good balance of coverage and accuracy

### High Threshold (0.7-0.9)

**Use when:**

* Accuracy is critical
* Automated apply without manual review
* Production environments

```yaml
llm:
  confidence_threshold: 0.8
  fallback_to_regex: false  # Don't apply uncertain changes
```

**Trade-off**: Fewer changes applied, but higher accuracy

## Interaction with Fallback

When `fallback_to_regex: true` (default), low-confidence LLM results trigger regex parsing:

```text
┌─────────────────────────────────────────────────────────────────┐
│                         Comment Input                           │
│                              │                                  │
│                              ▼                                  │
│                      ┌───────────────┐                          │
│                      │  LLM Parser   │                          │
│                      └───────────────┘                          │
│                              │                                  │
│                              ▼                                  │
│                  confidence >= threshold?                       │
│                     │              │                            │
│                    YES            NO                            │
│                     │              │                            │
│                     ▼              ▼                            │
│              ┌─────────┐   ┌─────────────┐                      │
│              │  Accept │   │ Regex       │                      │
│              │  LLM    │   │ Fallback    │                      │
│              │  Result │   │             │                      │
│              └─────────┘   └─────────────┘                      │
│                                  │                              │
│                                  ▼                              │
│                           regex match?                          │
│                           │          │                          │
│                          YES        NO                          │
│                           │          │                          │
│                           ▼          ▼                          │
│                     ┌─────────┐ ┌─────────┐                     │
│                     │ Accept  │ │ Reject  │                     │
│                     │ Regex   │ │ Comment │                     │
│                     └─────────┘ └─────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

### Disabling Fallback

For strict LLM-only parsing:

```yaml
llm:
  confidence_threshold: 0.7
  fallback_to_regex: false
```

With fallback disabled, low-confidence results are rejected entirely.

## Monitoring Confidence

### Check Fallback Rate

High fallback rates indicate the threshold may be too high:

```bash
pr-resolve apply 123 --llm-enabled --show-metrics
```

Output:

```text
Fallback rate: 15.2% (8 fallbacks)
```

**Interpretation:**

* < 5%: Threshold is appropriate
* 5-15%: Consider lowering threshold slightly
* \> 15%: Threshold may be too high for your comment style

### Per-Request Confidence

Export metrics for detailed analysis:

```bash
pr-resolve apply 123 --llm-enabled --show-metrics --metrics-output metrics.json
```

## Tuning Workflow

1. **Start with default (0.5)**:

   ```bash
   pr-resolve apply 123 --llm-enabled --show-metrics
   ```

2. **Check fallback rate**: If > 10%, try lowering threshold

3. **Check accuracy**: Review applied changes for correctness

4. **Adjust as needed**:

   ```bash
   # Lower threshold if too many fallbacks
   pr-resolve apply 123 --llm-confidence-threshold 0.4

   # Raise threshold if seeing incorrect parses
   pr-resolve apply 123 --llm-confidence-threshold 0.7
   ```

## Common Issues

### High Fallback Rate

**Symptom**: Fallback rate > 20%

**Causes:**

* Threshold too high for comment style
* Complex or non-standard comment formats
* LLM having trouble with specific patterns

**Solutions:**

* Lower confidence threshold
* Check if comments follow CodeRabbit format
* Review fallback comments for patterns

### Incorrect Parses

**Symptom**: Applied changes don't match comment intent

**Causes:**

* Threshold too low
* Ambiguous comments
* LLM misinterpretation

**Solutions:**

* Raise confidence threshold
* Enable stricter validation
* Review comment formatting

### No Changes Applied

**Symptom**: All comments rejected or fallback

**Causes:**

* Threshold too high
* LLM provider issues
* Non-actionable comments

**Solutions:**

* Lower confidence threshold
* Check LLM provider connectivity
* Verify comments contain code suggestions

## See Also

* [LLM Configuration](llm-configuration.md) - Full configuration reference
* [Troubleshooting](troubleshooting.md) - Common issues and solutions
* [Metrics Guide](metrics-guide.md) - Understanding metrics output
