# GitHub Actions Integration

This guide shows how to integrate the Review Bot Automator with GitHub Actions for automated conflict resolution.

## Quick Start

Add this workflow to `.github/workflows/pr-resolve.yml`:

```yaml
name: Apply CodeRabbit Suggestions

on:
  pull_request:
    types: [opened, synchronize]
  issue_comment:
    types: [created]

jobs:
  apply-suggestions:
    runs-on: ubuntu-latest
    if: |
      github.event_name == 'pull_request' ||
      (github.event_name == 'issue_comment' &&
       contains(github.event.comment.body, '/apply-suggestions'))

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Review Bot Automator
        run: pip install review-bot-automator

      - name: Apply Suggestions
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CR_LLM_ENABLED: 'true'
          CR_LLM_PROVIDER: 'anthropic'
          CR_LLM_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          CR_LLM_COST_BUDGET: '2.0'
        run: |
          pr-resolve apply ${{ github.event.pull_request.number || github.event.issue.number }} \
            --owner ${{ github.repository_owner }} \
            --repo ${{ github.event.repository.name }} \
            --show-metrics \
            --log-level INFO

      - name: Commit Changes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A
          git diff --staged --quiet || git commit -m "Apply CodeRabbit suggestions"
          git push
```

## Configuration Options

### Using Local Ollama (Free)

For organizations wanting to avoid API costs:

```yaml
jobs:
  apply-suggestions:
    runs-on: self-hosted  # Requires GPU-enabled runner

    services:
      ollama:
        image: ollama/ollama:latest
        ports:
          - 11434:11434
        options: --gpus all

    steps:
      - name: Pull Model
        run: curl -X POST http://localhost:11434/api/pull -d '{"name":"qwen2.5-coder:7b"}'

      - name: Apply Suggestions
        env:
          CR_LLM_ENABLED: 'true'
          CR_LLM_PROVIDER: 'ollama'
          CR_LLM_MODEL: 'qwen2.5-coder:7b'
        run: pr-resolve apply ${{ github.event.pull_request.number }}
```

### With Cost Controls

```yaml
- name: Apply Suggestions
  env:
    CR_LLM_ENABLED: 'true'
    CR_LLM_PROVIDER: 'anthropic'
    CR_LLM_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    CR_LLM_MODEL: 'claude-haiku-4-20250514'  # Cost-effective
    CR_LLM_COST_BUDGET: '1.0'  # $1 limit per PR
    CR_LLM_CONFIDENCE_THRESHOLD: '0.7'  # Higher quality
  run: |
    pr-resolve apply ${{ github.event.pull_request.number }} \
      --owner ${{ github.repository_owner }} \
      --repo ${{ github.event.repository.name }} \
      --show-metrics \
      --metrics-output metrics.json
```

### With Config File

```yaml
- name: Apply Suggestions
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    CR_LLM_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: |
    pr-resolve apply ${{ github.event.pull_request.number }} \
      --config .pr-resolve/ci-config.yaml
```

## Workflow Triggers

### On PR Open/Update

```yaml
on:
  pull_request:
    types: [opened, synchronize]
```

### On Comment Command

```yaml
on:
  issue_comment:
    types: [created]

jobs:
  apply-suggestions:
    if: |
      github.event.issue.pull_request &&
      contains(github.event.comment.body, '/apply-suggestions')
```

### Scheduled (Daily)

```yaml
on:
  schedule:
    - cron: '0 6 * * *'  # 6 AM UTC daily

jobs:
  process-open-prs:
    runs-on: ubuntu-latest
    steps:
      - name: Get Open PRs
        id: prs
        run: |
          prs=$(gh pr list --json number --jq '.[].number' | tr '\n' ' ')
          echo "prs=$prs" >> $GITHUB_OUTPUT
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Process Each PR
        run: |
          for pr in ${{ steps.prs.outputs.prs }}; do
            pr-resolve apply $pr --show-metrics || true
          done
```

## Secrets Configuration

Required secrets in repository settings:

| Secret | Required | Description |
|--------|----------|-------------|
| `GITHUB_TOKEN` | Auto | Built-in, no setup needed |
| `ANTHROPIC_API_KEY` | If using Anthropic | API key from console.anthropic.com |
| `OPENAI_API_KEY` | If using OpenAI | API key from platform.openai.com |

## Best Practices

### 1. Use Branch Protection

Ensure the workflow can push to PR branches:

```yaml
# In branch protection rules:
# - Allow force pushes: Yes (for github-actions[bot])
# - Or use a PAT instead of GITHUB_TOKEN
```

### 2. Add Status Checks

```yaml
- name: Report Status
  if: always()
  run: |
    if [ -f metrics.json ]; then
      echo "### PR Resolve Results" >> $GITHUB_STEP_SUMMARY
      cat metrics.json | jq -r '.summary | "- Applied: \(.successful_requests)\n- Cost: $\(.total_cost)"' >> $GITHUB_STEP_SUMMARY
    fi
```

### 3. Handle Failures Gracefully

```yaml
- name: Apply Suggestions
  continue-on-error: true
  id: apply
  run: pr-resolve apply ${{ github.event.pull_request.number }}

- name: Comment on Failure
  if: steps.apply.outcome == 'failure'
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: '⚠️ Failed to apply suggestions. Check workflow logs.'
      })
```

### 4. Cache Dependencies

```yaml
- name: Cache pip packages
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-pr-resolve

- name: Cache LLM responses
  uses: actions/cache@v4
  with:
    path: ~/.cache/pr-resolve
    key: ${{ runner.os }}-llm-cache-${{ github.sha }}
    restore-keys: |
      ${{ runner.os }}-llm-cache-
```

## Troubleshooting

### Workflow Not Triggering

* Check workflow permissions in repo settings
* Verify `on:` triggers match your use case
* Check branch protection rules

### Permission Denied

* Workflow needs `contents: write` permission
* Consider using a PAT for more permissions

### Rate Limiting

* Use `CR_LLM_COST_BUDGET` to limit API calls
* Consider using Ollama for high-volume repos
* Add delays between PR processing

## See Also

* [GitLab CI Integration](gitlab-ci.md) - GitLab CI/CD setup
* [Configuration](../configuration.md) - Full configuration reference
* [Cost Estimation](../cost-estimation.md) - Managing API costs
