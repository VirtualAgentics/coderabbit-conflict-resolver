# GitLab CI Integration

This guide shows how to integrate the Review Bot Automator with GitLab CI/CD for automated conflict resolution.

## Quick Start

Add this to your `.gitlab-ci.yml`:

```yaml
stages:
  - resolve

apply-suggestions:
  stage: resolve
  image: python:3.12-slim

  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

  variables:
    CR_LLM_ENABLED: "true"
    CR_LLM_PROVIDER: "anthropic"
    CR_LLM_COST_BUDGET: "2.0"

  before_script:
    - pip install review-bot-automator
    - git config user.name "GitLab CI"
    - git config user.email "ci@gitlab.com"

  script:
    - |
      pr-resolve apply $CI_MERGE_REQUEST_IID \
        --owner $CI_PROJECT_NAMESPACE \
        --repo $CI_PROJECT_NAME \
        --show-metrics \
        --log-level INFO
    - git add -A
    - git diff --staged --quiet || git commit -m "Apply CodeRabbit suggestions"
    - git push origin HEAD:$CI_MERGE_REQUEST_SOURCE_BRANCH

  environment:
    name: pr-resolve
```

## Configuration Options

### Using GitLab CI/CD Variables

Set these in Settings > CI/CD > Variables:

| Variable | Masked | Protected | Description |
|----------|--------|-----------|-------------|
| `GITLAB_TOKEN` | Yes | No | GitLab Personal Access Token |
| `ANTHROPIC_API_KEY` | Yes | No | Anthropic API key |
| `OPENAI_API_KEY` | Yes | No | OpenAI API key |
| `CR_LLM_API_KEY` | Yes | No | LLM provider API key |

### With Ollama (Self-Hosted Runner)

For private/offline deployments:

```yaml
apply-suggestions:
  stage: resolve
  tags:
    - gpu  # Requires GPU-enabled runner

  services:
    - name: ollama/ollama:latest
      alias: ollama

  variables:
    CR_LLM_ENABLED: "true"
    CR_LLM_PROVIDER: "ollama"
    CR_LLM_MODEL: "qwen2.5-coder:7b"
    OLLAMA_BASE_URL: "http://ollama:11434"

  before_script:
    - pip install review-bot-automator
    - curl -X POST http://ollama:11434/api/pull -d '{"name":"qwen2.5-coder:7b"}'

  script:
    - pr-resolve apply $CI_MERGE_REQUEST_IID --owner $CI_PROJECT_NAMESPACE --repo $CI_PROJECT_NAME
```

### With Config File

```yaml
apply-suggestions:
  script:
    - |
      pr-resolve apply $CI_MERGE_REQUEST_IID \
        --owner $CI_PROJECT_NAMESPACE \
        --repo $CI_PROJECT_NAME \
        --config .pr-resolve/gitlab-config.yaml
```

## Pipeline Triggers

### On Merge Request Events

```yaml
rules:
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### On Manual Trigger

```yaml
rules:
  - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    when: manual
    allow_failure: true
```

### Scheduled Processing

```yaml
# In CI/CD > Schedules
# Cron: 0 6 * * *  # 6 AM daily

process-open-mrs:
  stage: resolve
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"

  script:
    - |
      for mr in $(glab mr list --state opened --json iid | jq -r '.[].iid'); do
        pr-resolve apply $mr || true
      done
```

## Authentication

### GitLab API Token

Required permissions:

* `api` - Full API access
* `write_repository` - Push changes

```yaml
variables:
  GITLAB_TOKEN: $GITLAB_ACCESS_TOKEN
```

### Push to Source Branch

```yaml
script:
  - git remote set-url origin "https://oauth2:${GITLAB_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}.git"
  - git push origin HEAD:$CI_MERGE_REQUEST_SOURCE_BRANCH
```

## Best Practices

### 1. Use Artifacts for Reports

```yaml
apply-suggestions:
  script:
    - |
      pr-resolve apply $CI_MERGE_REQUEST_IID \
        --show-metrics \
        --metrics-output metrics.json

  artifacts:
    paths:
      - metrics.json
    reports:
      metrics: metrics.json
    expire_in: 1 week
```

### 2. Add MR Comments

```yaml
apply-suggestions:
  after_script:
    - |
      if [ -f metrics.json ]; then
        cost=$(jq -r '.summary.total_cost' metrics.json)
        applied=$(jq -r '.summary.successful_requests' metrics.json)
        glab mr note $CI_MERGE_REQUEST_IID \
          --message "Applied $applied suggestions (cost: \$$cost)"
      fi
```

### 3. Handle Failures

```yaml
apply-suggestions:
  script:
    - pr-resolve apply $CI_MERGE_REQUEST_IID || exit_code=$?
    - |
      if [ "${exit_code:-0}" -ne 0 ]; then
        glab mr note $CI_MERGE_REQUEST_IID \
          --message "⚠️ Failed to apply suggestions. Check pipeline logs."
        exit $exit_code
      fi
```

### 4. Cache Dependencies

```yaml
apply-suggestions:
  cache:
    key: pr-resolve-$CI_COMMIT_REF_SLUG
    paths:
      - .cache/pip
      - .cache/pr-resolve

  variables:
    PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
```

## Complete Example

```yaml
stages:
  - resolve

.pr-resolve-base:
  image: python:3.12-slim

  variables:
    CR_LLM_ENABLED: "true"
    CR_LLM_PROVIDER: "anthropic"
    CR_LLM_MODEL: "claude-haiku-4-20250514"
    CR_LLM_COST_BUDGET: "2.0"
    CR_LLM_CONFIDENCE_THRESHOLD: "0.7"
    PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

  cache:
    key: pr-resolve-cache
    paths:
      - .cache/

  before_script:
    - pip install review-bot-automator
    - git config user.name "GitLab CI"
    - git config user.email "ci@gitlab.com"

apply-suggestions:
  extends: .pr-resolve-base
  stage: resolve

  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      when: manual
      allow_failure: true

  script:
    - |
      pr-resolve apply $CI_MERGE_REQUEST_IID \
        --show-metrics \
        --metrics-output metrics.json \
        --log-level INFO

    - git add -A
    - |
      if ! git diff --staged --quiet; then
        git commit -m "Apply CodeRabbit suggestions

        Applied by GitLab CI pipeline $CI_PIPELINE_ID"
        git remote set-url origin "https://oauth2:${GITLAB_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}.git"
        git push origin HEAD:$CI_MERGE_REQUEST_SOURCE_BRANCH
      fi

  after_script:
    - |
      if [ -f metrics.json ]; then
        cost=$(jq -r '.summary.total_cost' metrics.json)
        applied=$(jq -r '.summary.successful_requests' metrics.json)
        glab mr note $CI_MERGE_REQUEST_IID \
          --message "✅ Applied $applied suggestions (cost: \$$cost)"
      fi

  artifacts:
    paths:
      - metrics.json
    expire_in: 1 week
```

## Troubleshooting

### Pipeline Not Triggering

* Check `rules:` conditions match your use case
* Verify merge request is not from a fork
* Check CI/CD is enabled for merge requests

### Permission Denied

* Verify `GITLAB_TOKEN` has required scopes
* Check branch protection settings
* Ensure token is not expired

### Push Fails

* Check branch is not protected
* Verify token has `write_repository` permission
* Check for merge conflicts

## See Also

* [GitHub Actions Integration](github-actions.md) - GitHub Actions setup
* [Configuration](../configuration.md) - Full configuration reference
* [Cost Estimation](../cost-estimation.md) - Managing API costs
