# Scripts Directory

This directory contains utility scripts for maintaining and managing the CodeRabbit Conflict Resolver project.

## GitHub Actions SHA Management

### Scripts

#### `verify-workflow-shas.sh`
Comprehensive script to verify and optionally fix GitHub Actions SHAs in all workflow files.

**Usage:**
```bash
# Check all SHAs
./scripts/verify-workflow-shas.sh

# Check and fix all SHAs automatically
./scripts/verify-workflow-shas.sh -f

# Verbose output
./scripts/verify-workflow-shas.sh -v

# Help
./scripts/verify-workflow-shas.sh -h
```

**Features:**
- Validates SHA format (40 characters, hex)
- Verifies SHA exists in the repository
- Can automatically fix malformed SHAs
- Provides detailed reporting
- Supports all workflow files

#### `get-action-sha.sh`
Helper script to get the correct SHA for any GitHub Action.

**Usage:**
```bash
# Get SHA for a specific version
./scripts/get-action-sha.sh actions/checkout v5.0.0

# Get SHA for latest release
./scripts/get-action-sha.sh actions/checkout latest

# Get SHA for a branch
./scripts/get-action-sha.sh actions/checkout main
```

**Features:**
- Gets SHA for specific versions, branches, or latest releases
- Validates SHA format and existence
- Provides usage examples for workflows
- Supports all GitHub Actions

### Prerequisites

These scripts require:
- `gh` (GitHub CLI) - [Installation guide](https://cli.github.com/)
- `jq` - JSON processor
- GitHub authentication (`gh auth login`)

### Installation

```bash
# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Install jq
sudo apt install jq

# Authenticate with GitHub
gh auth login
```

### Common Use Cases

#### 1. Verify All Workflow SHAs
```bash
# Check all SHAs without making changes
./scripts/verify-workflow-shas.sh
```

#### 2. Fix Malformed SHAs
```bash
# Automatically fix all malformed SHAs
./scripts/verify-workflow-shas.sh -f
```

#### 3. Get SHA for New Action
```bash
# Get SHA for a new action you want to use
./scripts/get-action-sha.sh actions/setup-node v4.0.0
```

#### 4. Update Action Version
```bash
# Get SHA for newer version
./scripts/get-action-sha.sh actions/checkout v6.0.0

# Then update the workflow file manually
```

### Integration with CI/CD

You can integrate these scripts into your CI/CD pipeline:

```yaml
# .github/workflows/verify-shas.yml
name: Verify Workflow SHAs

on:
  pull_request:
    paths:
      - '.github/workflows/**'

jobs:
  verify-shas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup GitHub CLI
        uses: actions/setup-go@v4
        with:
          go-version: '1.21'
      - name: Install GitHub CLI
        run: |
          go install github.com/cli/cli/v2/cmd/gh@latest
      - name: Verify SHAs
        run: ./scripts/verify-workflow-shas.sh
```

### Troubleshooting

#### Error: "GitHub CLI not found"
```bash
# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
```

#### Error: "Not authenticated"
```bash
# Authenticate with GitHub
gh auth login
```

#### Error: "jq not found"
```bash
# Install jq
sudo apt install jq
```

#### Error: "Permission denied"
```bash
# Make scripts executable
chmod +x scripts/*.sh
```

### Best Practices

1. **Regular Verification**: Run SHA verification before major releases
2. **Automated Checks**: Integrate into CI/CD pipeline
3. **Version Updates**: Update action versions regularly
4. **Documentation**: Keep SHA management documentation current
5. **Testing**: Test workflows after SHA updates

### Related Documentation

- [GitHub Actions SHA Management Guide](../docs/github-actions-sha-management.md)
- [Architecture Documentation](../docs/architecture.md)
- [Contributing Guidelines](../CONTRIBUTING.md)

### Support

If you encounter issues with these scripts:

1. Check the prerequisites are installed
2. Verify GitHub authentication
3. Check the script output for specific error messages
4. Review the documentation
5. Create an issue in the repository
