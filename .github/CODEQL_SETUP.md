# CodeQL Setup

## Status

✅ **CodeQL default setup has been disabled** in GitHub repository settings.

The custom CodeQL workflow in `.github/workflows/security.yml` is now active and will run on:
- Pull requests to `main` and `develop` branches
- Weekly schedule (Mondays at 2 AM)

## Custom Workflow Benefits

- **Control:** Runs on specific events (PRs, schedule)
- **Integration:** Part of our comprehensive security workflow
- **Customization:** Can add custom queries and configurations
- **Consistency:** Aligned with other security checks (Bandit, Safety, pip-audit)

## Workflow Configuration

The CodeQL job in `security.yml`:
- Scans Python code
- Uses CodeQL v4.31.0
- Uploads results to GitHub Security tab
- Runs in parallel with other security checks

## Troubleshooting

If CodeQL fails with "default setup is enabled" error:
1. Go to repository **Settings** → **Code security and analysis**
2. Find "CodeQL analysis" section
3. Ensure default setup is **Disabled**
4. Re-run the workflow

## Monitoring

Check CodeQL results in:
- **Security tab** → Code scanning alerts
- **Actions tab** → Security workflow runs
- **Pull request checks** → Security/codeql status
