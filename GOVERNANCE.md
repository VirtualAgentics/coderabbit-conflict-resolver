# Project Governance

This document describes the governance model for the Review Bot Automator project.

## Governance Model

Review Bot Automator uses a **Benevolent Dictator** governance model. The project owner makes all final decisions regarding the project's direction, features, and releases.

This model is appropriate for the project's current stage as a single-maintainer open source project. The governance model may evolve as the project grows and attracts more contributors.

## Decision Making

### How Decisions Are Made

1. **Feature Requests**: Submitted via GitHub Issues, reviewed by the project owner
2. **Pull Requests**: Reviewed by the project owner, who has final merge authority
3. **Releases**: Determined and executed by the project owner
4. **Security Issues**: Handled privately per [SECURITY.md](SECURITY.md), with project owner making final decisions

### Decision Criteria

Decisions are made based on:

- Alignment with project goals and roadmap
- Code quality and test coverage requirements
- Security implications
- Maintainability and long-term sustainability
- Community benefit

### Escalation

For the current single-maintainer model, the project owner's decision is final. Contributors who disagree with a decision may:

1. Discuss concerns in the relevant GitHub Issue or PR
2. Contact the project owner directly at <bdc@virtualagentics.ai>
3. Fork the project under the MIT license terms

## Roles and Responsibilities

### Project Owner/Maintainer

**Current**: VirtualAgentics (<bdc@virtualagentics.ai>)

**Responsibilities**:

- Final decision authority on all project matters
- Code review and merge authority for all PRs
- Release management and versioning
- Security vulnerability response (per SECURITY.md)
- Community management and Code of Conduct enforcement
- Infrastructure and CI/CD management
- Documentation maintenance

**Access Level**: Full admin access to GitHub repository, PyPI, and all project infrastructure

### Contributors

**Who**: Anyone who submits pull requests, issues, or participates in discussions

**Responsibilities**:

- Follow [CONTRIBUTING.md](CONTRIBUTING.md) guidelines
- Sign-off commits with DCO (Developer Certificate of Origin)
- Adhere to [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Respond to review feedback on their contributions
- Write tests for new functionality

**Access Level**: Read access to repository, ability to fork and submit PRs

### Reviewers (Future Role)

As the project grows, trusted contributors may be granted reviewer status:

- Code review authority (but not merge authority)
- Triage issues and PRs
- Mentor new contributors

## Bus Factor

### Current Status

The project currently has a bus factor of **1** (single maintainer). This is acknowledged and documented here for transparency.

### Mitigation Measures

1. **Organizational Ownership**: The repository is owned by the VirtualAgentics GitHub organization, not a personal account
2. **Documentation**: All critical processes are documented in the repository
3. **Open Source License**: MIT license ensures the project can be forked and continued by anyone
4. **No Single Points of Failure**: All project artifacts are in the public repository
5. **Succession Plan**: See below

## Continuity and Succession

### Emergency Contact

If the project owner is unresponsive for an extended period:

- **Email**: <bdc@virtualagentics.ai>
- **GitHub**: Open an issue with `[URGENT]` prefix
- **Organization**: Contact VirtualAgentics organization admins

### Succession Plan

In the event the current maintainer is unable to continue:

1. **GitHub Organization**: VirtualAgentics organization ownership ensures admin access can be transferred
2. **PyPI**: Trusted publishing via GitHub Actions; new maintainers can be added to the organization
3. **Documentation**: All processes documented in repository
4. **Secrets**: Critical credentials (API keys, tokens) stored securely outside the repository; succession would require regenerating these

### What Happens If Maintainer Is Unavailable

The project can continue with minimal interruption because:

- All code is open source (MIT license)
- CI/CD runs automatically via GitHub Actions
- Releases are automated via tagged commits
- Documentation is self-contained in the repository

Community members can:

- Fork the repository and continue development
- Create issues to signal need for new maintainership
- Contact VirtualAgentics organization for ownership transfer

## Changes to Governance

This governance document may be updated by the project owner. Significant changes will be:

1. Announced in a GitHub Issue
2. Open for community feedback for at least 7 days
3. Documented in the repository changelog

## Related Documents

- [CONTRIBUTING.md](CONTRIBUTING.md) - How to contribute
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) - Community standards
- [SECURITY.md](SECURITY.md) - Security policy and vulnerability reporting
- [docs/planning/ROADMAP.md](docs/planning/ROADMAP.md) - Project roadmap
