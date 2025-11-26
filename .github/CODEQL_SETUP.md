# CodeQL Setup

## Status

✅ **CodeQL custom workflow is active** with optimized configuration.

The CodeQL job in `.github/workflows/security.yml` runs on:

* Pull requests to `main` and `develop` branches
* Weekly schedule (Mondays at 2 AM UTC)

## Performance Optimization

**🚀 CodeQL analysis is ~30% faster** thanks to removing unnecessary dependency installation.

**Key Insight:** For Python, CodeQL analyzes source code directly without needing runtime dependencies. The workflow has been optimized to:

* ❌ **Skip Python dependency installation** (saves ~21 seconds per run)
* ✅ **Use custom configuration file** (`.github/codeql/codeql-config.yml`)
* ✅ **Use security-extended query suite** (enhanced security coverage)
* ✅ **Verify SARIF upload success** (better monitoring)

### Performance Metrics

| Metric | Before | After | Improvement |
| ------ | ------ | ----- | ----------- |
| Job Duration | 86 seconds | ~60-65 seconds | 24-30% |
| Dependency Install | 21 seconds | 0 seconds | Eliminated |
| Analysis Quality | Default queries | security-extended | Enhanced |

### Why dependencies aren't needed

For Python, CodeQL works by:

1. Extracting the Abstract Syntax Tree (AST) from source code
2. Building a semantic database of code structure
3. Running security queries against this database
4. **Does NOT need** imports to be resolvable or packages installed

This is different from compiled languages (C/C++, Java) which require a build step.

## Custom Configuration

The CodeQL analysis uses a custom configuration file at `.github/codeql/codeql-config.yml`:

### Query Suites

* **security-extended**: Enhanced security queries including additional patterns
  * Covers: CWE top 25, OWASP top 10, GitHub-specific security patterns
* **security-and-quality**: Combines security with code quality checks
  * Helps identify maintainability issues that could lead to security bugs

### Path Filters

* **Analyzed**: `src/review_bot_automator/` (production code)
* **Excluded**: `tests/`, `docs/`, scripts, build artifacts
* **Benefit**: Focused analysis, reduced false positives, faster scanning

### Query Filters

* Excludes common Python CLI false positives
* Customized for project-specific patterns
* Can be extended with custom queries

## Workflow Configuration

The CodeQL job:

* **Language**: Python only (extensible to other languages)
* **CodeQL Version**: v4.31.0 (pinned with SHA for security)
* **Timeout**: 30 minutes (typical runtime: 1-2 minutes)
* **Permissions**: Minimal (actions:read, contents:read, security-events:write)
* **Upload**: SARIF results to GitHub Security tab
* **Summary**: Provides analysis details in workflow output

## Custom Workflow Benefits

* **Control**: Runs on specific events (PRs, schedule)
* **Integration**: Part of comprehensive security workflow
* **Customization**: Custom queries and configurations via config file
* **Consistency**: Aligned with other security checks (Bandit, Safety, pip-audit)
* **Performance**: Optimized for Python analysis (no unnecessary steps)
* **Visibility**: Workflow summaries show analysis status and optimization metrics

## Monitoring

### Check CodeQL Results

### Security Tab

```text
Repository → Security → Code scanning alerts

```

View all detected security vulnerabilities and code quality issues.

### Actions Tab

```text
Repository → Actions → Security workflow

```

Monitor workflow runs and analysis performance.

### Pull Request Checks

```text
PR → Checks → Security / codeql (python)

```

View CodeQL status directly in pull requests.

### Workflow Summary

After each run, the workflow provides a detailed summary including:

* Analysis completion status
* Query suite used (security-extended)
* Configuration file path
* Link to code scanning alerts
* Optimization metrics

## Troubleshooting

### Error: "Default setup is enabled"

If CodeQL fails with this error:

1. Go to repository **Settings** → **Code security and analysis**
2. Find "CodeQL analysis" section
3. Ensure default setup is **Disabled**
4. Re-run the workflow

**Why this matters:** GitHub's default CodeQL setup conflicts with custom workflows. We use a custom workflow for better control and integration with our security pipeline.

### Error: "Configuration file not found"

If CodeQL fails to find the config file:

1. Verify `.github/codeql/codeql-config.yml` exists
2. Check file path in workflow is correct: `./.github/codeql/codeql-config.yml`
3. Ensure file is committed to the repository

### Warning: "Query suite not found"

If query suite warnings appear:

1. Verify `security-extended` is spelled correctly
2. Check CodeQL version supports the query suite (v4.31.0+)
3. Review CodeQL action documentation for available suites

### No Results Uploaded

If SARIF results don't appear in Security tab:

1. Check workflow permissions include `security-events: write`
2. Verify analysis step completed successfully (check logs)
3. Confirm repository has code scanning enabled in settings
4. Check for API errors in workflow logs

## Maintenance

### Updating CodeQL Version

To update CodeQL:

1. Check [github/codeql-action releases](<https://github.com/github/codeql-action/releases)>
2. Update SHA hash in `.github/workflows/security.yml`
3. Test with a pull request
4. Monitor for any breaking changes

### Adding Custom Queries

To add project-specific queries:

1. Create `.github/codeql/queries/` directory
2. Add `.ql` files with custom queries
3. Reference in `.github/codeql/codeql-config.yml`:

   ```yaml
   queries:
     * uses: security-extended
     * uses: ./.github/codeql/queries/
   ```

### Extending to Other Languages

To scan additional languages:

1. Add language to matrix in `security.yml`:

   ```yaml
   matrix:
     language: ["python", "javascript", "go"]

   ```

2. Update config file with language-specific settings
3. Adjust path filters as needed

## Related Documentation

* [GitHub CodeQL Documentation](<https://docs.github.com/en/code-security/code-scanning/automatically-scanning-your-code-for-vulnerabilities-and-errors/about-code-scanning-with-codeql)>
* [CodeQL Query Suites](<https://docs.github.com/en/code-security/code-scanning/automatically-scanning-your-code-for-vulnerabilities-and-errors/built-in-codeql-query-suites)>
* [Issue #43: CodeQL Optimization](<https://github.com/VirtualAgentics/review-bot-automator/issues/43)>
