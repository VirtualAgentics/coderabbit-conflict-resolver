# Privacy Architecture - Local LLM Operation

## Executive Summary

This document establishes the privacy architecture for Review Bot Automator's LLM integration, with a focus on reducing third-party data exposure through local LLM operation using Ollama.

### Purpose

This document provides:

* Foundation for privacy-preserving LLM operation
* Data flow analysis for local vs. API-based providers
* Compliance guidance for regulated industries
* Privacy verification procedures
* Risk assessment for different deployment scenarios

### Privacy-First Approach Rationale

Review Bot Automator processes source code and review comments that may contain:

* Proprietary business logic
* Security-sensitive implementations
* Personal Identifiable Information (PII)
* Protected Health Information (PHI)
* Trade secrets and intellectual property

**Important Context**: This tool works with GitHub pull requests, which means your code is already on GitHub and accessible to CodeRabbit (or other review bots). The privacy benefit of using Ollama is **reducing third-party LLM vendor exposure**, not achieving complete isolation.

When using cloud-based LLM providers (OpenAI, Anthropic), your code is exposed to:

* GitHub (required for PR workflow)
* CodeRabbit (required for review comments)
* LLM vendor (OpenAI/Anthropic)

**Local operation with Ollama reduces this to**:

* GitHub (required for PR workflow)
* CodeRabbit (required for review comments)
* ~~LLM vendor~~ (eliminated - processed locally)

### Key Stakeholders

* **Developers**: Primary users who require code privacy
* **Security Team**: Ensures data protection policies are enforced
* **Compliance Team**: Ensures adherence to GDPR, HIPAA, SOC2, etc.
* **Legal Team**: Manages intellectual property and data residency requirements

---

## Table of Contents

* [Privacy Principles](#privacy-principles)
* [Data Flow Comparison](#data-flow-comparison)
* [Provider Comparison Matrix](#provider-comparison-matrix)
* [Compliance & Regulations](#compliance--regulations)
* [Privacy Guarantees](#privacy-guarantees)
* [Threat Model for Privacy](#threat-model-for-privacy)
* [Security Controls for Local Models](#security-controls-for-local-models)
* [Privacy Verification](#privacy-verification)
* [Related Documentation](#related-documentation)

---

## Privacy Principles

The following privacy principles guide our architecture and provider recommendations:

### 1. Data Minimization

**Principle**: Only process data that is strictly necessary for the operation.

**Implementation**:

* LLM providers only receive review comments and relevant code context
* No full repository access
* No user authentication data sent to LLMs
* Minimal metadata in requests

**Local vs API**:

* **Ollama (Local)**: Review comments processed locally, no transmission to LLM vendor
* **API Providers**: Review comments sent to third-party LLM servers (OpenAI/Anthropic)

**Note**: GitHub API access is required for both options to fetch PR review comments.

### 2. Data Sovereignty

**Principle**: Minimize data processing in third-party data centers.

**Implementation**:

* **Ollama**: LLM inference on user's hardware (review comments processed locally)
* **API Providers**: LLM inference in provider's data centers (US, EU, etc.)

**Rationale**: Regulatory compliance (GDPR, data residency laws) often benefits from reducing the number of third-party processors.

**Important**: Your code is already on GitHub (required for PR workflow), so complete data sovereignty is not possible with this tool.

### 3. Third-Party Exposure Reduction

**Principle**: Minimize the number of third parties with access to sensitive code and review comments.

**Reality Check**:

* **GitHub**: Has access (required - your code lives here)
* **CodeRabbit**: Has access (required - generates review comments)
* **LLM Vendor**: This is what we can control

**Implementation**:

* **Ollama**: Eliminates LLM vendor from the access chain
* **API Providers**: Adds OpenAI/Anthropic to the access chain

**Rationale**: Every additional third party increases the risk of data breaches, unauthorized access, and compliance complexity. Ollama removes one third party (LLM vendor) from the chain.

### 4. Transparency

**Principle**: Users should know exactly where their data goes and how it's processed.

**Implementation**:

* Clear documentation of data flows for each provider
* Privacy verification tooling (`scripts/verify_privacy.sh`)
* No hidden telemetry or analytics
* **Honest disclosure**: GitHub and CodeRabbit have access (required for PR workflow)

**Rationale**: Informed consent requires transparency about data handling practices.

### 5. User Control

**Principle**: Users choose their privacy/performance trade-off.

**Implementation**:

* 5 provider options with varying privacy levels
* Easy switching between providers via presets
* Clear privacy comparison matrix (see below)

**Rationale**: Different use cases have different privacy requirements. We empower users to make informed decisions.

---

## Data Flow Comparison

### Local Model (Ollama) - Reduced Third-Party Exposure

```text
┌──────────────────────────────────────────────────────────────────┐
│  Internet (GitHub API - Required)                                │
│                                                                   │
│  ┌──────────────┐         ┌─────────────────┐                   │
│  │  GitHub PR   │◀───────▶│  CodeRabbit     │                   │
│  │  (Your Code) │  Review │  (Review Bot)   │                   │
│  └──────┬───────┘         └─────────────────┘                   │
│         │                                                         │
└─────────┼─────────────────────────────────────────────────────────┘
          │ HTTPS (Fetch PR comments)
          │
┌─────────▼─────────────────────────────────────────────────────────┐
│  Your Machine (localhost)                                         │
│                                                                    │
│  ┌──────────────┐         ┌─────────────────┐                    │
│  │  pr-resolve  │────────▶│  GitHub API     │                    │
│  │  (Fetch)     │         │  Client         │                    │
│  └──────┬───────┘         └─────────────────┘                    │
│         │                                                          │
│         │ Review Comments                                         │
│         │                                                          │
│  ┌──────▼───────┐         ┌─────────────────┐                    │
│  │  pr-resolve  │────────▶│  Ollama Server  │                    │
│  │  (Process)   │  HTTP   │  (Local LLM)    │                    │
│  └──────────────┘  :11434 └─────────────────┘                    │
│                                                                    │
│  ✅ LLM inference stays local (no OpenAI/Anthropic)               │
│  ✅ No LLM vendor API keys required                               │
│  ✅ No per-request LLM costs                                      │
│  ⚠️  GitHub API access required (code already on GitHub)          │
│  ⚠️  CodeRabbit has access (generates review comments)            │
│  ⚠️  Internet required to fetch PR comments                       │
└────────────────────────────────────────────────────────────────────┘

```

### API-Based Models - Additional Third-Party Exposure

```text
┌──────────────────────────────────────────────────────────────────┐
│  Internet (GitHub API - Required)                                │
│                                                                   │
│  ┌──────────────┐         ┌─────────────────┐                   │
│  │  GitHub PR   │◀───────▶│  CodeRabbit     │                   │
│  │  (Your Code) │  Review │  (Review Bot)   │                   │
│  └──────┬───────┘         └─────────────────┘                   │
│         │                                                         │
└─────────┼─────────────────────────────────────────────────────────┘
          │ HTTPS (Fetch PR comments)
          │
┌─────────▼─────────────────────────────────────────────────────────┐
│  Your Machine (localhost)                                         │
│                                                                    │
│  ┌──────────────┐         ┌─────────────────┐                    │
│  │  pr-resolve  │────────▶│  GitHub API     │                    │
│  │  (Fetch)     │         │  Client         │                    │
│  └──────┬───────┘         └─────────────────┘                    │
│         │                                                          │
│         │ Review Comments                                         │
│         │                                                          │
│  ┌──────▼───────┐                                                 │
│  │  pr-resolve  │─────────────────────────────────────────────────┼──┐
│  │  (Process)   │  HTTPS (API key, comments)                      │  │
│  └──────────────┘                                                 │  │
│                                                                    │  │
└────────────────────────────────────────────────────────────────────┘  │
                                                                         │
                     ════════════════════════════════════════════════════▼═══
                          Internet (TLS Encrypted to LLM Vendor)
                     ════════════════════════════════════════════════════╪═══
                                                                         │
┌────────────────────────────────────────────────────────────────────────▼───┐
│  LLM Provider Data Center (OpenAI/Anthropic - US, EU, etc.)               │
│                                                                             │
│                           ┌─────────────────┐                             │
│                           │  API Gateway    │                             │
│                           └────────┬────────┘                             │
│                                    │                                       │
│                           ┌────────▼────────┐                             │
│                           │  LLM Service    │                             │
│                           │  (GPT-4/Claude) │                             │
│                           └────────┬────────┘                             │
│                                    │ Response                             │
│                                                                             │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
                     ════════════════▼═════════════════
                          Internet (TLS Encrypted)
                     ════════════════╪═════════════════
                                     │
┌────────────────────────────────────▼─────────────────────────────────┐
│  Your Machine                                                         │
│                           ┌─────────────────┐                        │
│                           │  pr-resolve     │                        │
│                           │  (Apply fixes)  │                        │
│                           └─────────────────┘                        │
│                                                                       │
│  ⚠️  GitHub API access required (code already on GitHub)             │
│  ⚠️  CodeRabbit has access (generates review comments)               │
│  ⚠️  Internet required to fetch PR comments                          │
│  ❌ ADDITIONAL: Review comments sent to LLM vendor                   │
│  ❌ ADDITIONAL: Stored on LLM vendor servers (temp/permanent)        │
│  ❌ ADDITIONAL: Subject to LLM vendor data retention policies        │
│  ❌ Requires LLM vendor API key management                           │
│  ❌ Subject to rate limits                                           │
│  💰 Costs per LLM request                                            │
└───────────────────────────────────────────────────────────────────────┘

```

### Key Differences

| Aspect | Ollama (Local) | API Providers |
| -------- | --------------- | --------------- |
| **LLM Inference Location** | Your machine (localhost) | LLM vendor servers |
| **Third-Party LLM Vendor** | ❌ None | ✅ OpenAI/Anthropic |
| **GitHub/CodeRabbit Access** | ⚠️ Yes (required) | ⚠️ Yes (required) |
| **Internet Required** | ✅ Yes (to fetch PRs) | ✅ Yes (PRs + LLM API) |
| **Data Retention (LLM)** | You control | Vendor policy (30-90 days) |
| **Regulatory Compliance** | Simpler (one fewer processor) | More complex (additional processor) |
| **Cost** | Hardware only | Hardware + per-request fees |
| **Privacy Benefit** | Removes LLM vendor exposure | LLM vendor sees all comments |

---

## Provider Comparison Matrix

Comprehensive comparison of all 5 supported LLM providers across privacy dimensions:

| Provider | LLM Vendor Exposure | GitHub API Required | Cost | Best For |
| ---------- | --------------------- | --------------------- | ------ | ---------- |
| **Ollama** | ✅ **None** (localhost) | ✅ Yes | ✅ **Free** | Minimizing third-party exposure, compliance, cost savings |
| **OpenAI API** | ❌ OpenAI (US) | ✅ Yes | 💰 Low (~$0.01/PR) | Production, budget-conscious |
| **Anthropic API** | ❌ Anthropic (US) | ✅ Yes | 💰 Medium | Quality, caching benefits |
| **Claude CLI** | ❌ Anthropic (US) | ✅ Yes | 💰 Subscription | Interactive, convenience |
| **Codex CLI** | ❌ GitHub/OpenAI | ✅ Yes | 💰 Subscription (Copilot) | GitHub integration, free with Copilot |

### Privacy Ranking (by Third-Party Exposure)

1. **🥇 Ollama** - Best Privacy (GitHub + CodeRabbit only)
2. **🥈 OpenAI/Anthropic API** - Moderate Privacy (GitHub + CodeRabbit + LLM vendor)
3. **🥉 Claude CLI/Codex CLI** - Moderate Privacy (GitHub + CodeRabbit + LLM vendor)

**Note**: All options require GitHub API access and CodeRabbit has access to your code. The privacy difference is whether an additional LLM vendor (OpenAI/Anthropic) also gets access to review comments.

### Data Retention Policies (API Providers)

**OpenAI**:

* API requests: 30 days retention (for abuse monitoring)
* Can opt out of training data usage
* See: <https://openai.com/policies/api-data-usage-policies>

**Anthropic**:

* API requests: Not used for training by default
* 90 days retention for Trust & Safety
* See: <https://www.anthropic.com/legal/commercial-terms>

**GitHub (Codex CLI)**:

* Subject to GitHub's Privacy Statement
* Integrated with Copilot subscription
* See: <https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement>

**Important**: These policies may change. Always review current terms before use in regulated environments.

---

## Compliance & Regulations

### GDPR (General Data Protection Regulation)

**Requirements**:

* Personal data must be processed lawfully, fairly, and transparently
* Data minimization principle
* Right to erasure ("right to be forgotten")
* Data sovereignty (EU data stays in EU)

**Reality for This Tool**:

* ⚠️ **Code is on GitHub** - Already accessible to GitHub (US-based)
* ⚠️ **CodeRabbit processes code** - Review bot has access
* ⚠️ **Data Processing Agreements needed** - For GitHub, CodeRabbit

**Ollama Additional Benefits**:

* ✅ **Reduces processors** - Eliminates one additional data processor (LLM vendor)
* ✅ **Simplifies DPA chain** - No additional agreement for LLM vendor
* ✅ **Reduces cross-border transfers** - LLM processing stays local

**API Provider Additional Considerations**:

* ⚠️ **Adds another data processor** - OpenAI/Anthropic to DPA chain
* ⚠️ **Additional cross-border transfer** - Review comments to LLM vendor
* ⚠️ **Check provider's GDPR compliance** - Requires additional legal review

### HIPAA (Health Insurance Portability and Accountability Act)

**Requirements**:

* Protected Health Information (PHI) must remain secure
* Business Associate Agreements (BAA) required for third parties
* Audit trails and access controls

**Reality for This Tool**:

* ⚠️ **Code on GitHub** - BAA required with GitHub if PHI in code
* ⚠️ **CodeRabbit processes code** - BAA required with CodeRabbit
* ⚠️ **If PHI in code, already exposed** - GitHub and CodeRabbit have access

**Ollama Additional Benefits**:

* ✅ **Reduces BAA requirements** - No additional BAA for LLM vendor
* ✅ **Simpler compliance chain** - One fewer business associate

**API Provider Additional Considerations**:

* ⚠️ **Another BAA required** - Must sign BAA with OpenAI/Anthropic
* ⚠️ **Check HIPAA-eligible services** - Not all API tiers support HIPAA
* ⚠️ **Additional costs** - HIPAA-compliant tiers often more expensive
* ❌ **Verify current HIPAA support** - OpenAI/Anthropic support varies

### SOC 2 (Service Organization Control)

**Requirements**:

* Security, availability, processing integrity, confidentiality, privacy
* Third-party service providers must be audited

**Reality for This Tool**:

* ⚠️ **GitHub assessment required** - Vendor risk for GitHub
* ⚠️ **CodeRabbit assessment required** - Vendor risk for review bot

**Ollama Additional Benefits**:

* ✅ **Reduces vendor assessments** - One fewer vendor (no LLM vendor)
* ✅ **Simpler SOC 2 scope** - LLM processing under your control

**API Provider Additional Considerations**:

* ⚠️ **Another vendor assessment** - OpenAI/Anthropic SOC 2 review needed
* ⚠️ **SOC 2 reports must be reviewed** - Ensure Type II reports available
* ⚠️ **Continuous monitoring** - Provider's compliance status may change

---

## Privacy Guarantees

### Ollama Local Model Guarantees

When using Ollama with Review Bot Automator, you have the following privacy guarantees **for LLM inference**:

**Important Context**: This tool requires GitHub API access to fetch PR comments. Your code is already on GitHub. These guarantees apply to the LLM processing step only.

#### 1. LLM Inference Isolation

* **All LLM communication occurs on localhost** (127.0.0.1 / ::1)
* No external network connections initiated by Ollama during inference
* Can be verified with `scripts/verify_privacy.sh`
* ⚠️ **GitHub API calls still occur** (required to fetch PR comments)

#### 2. LLM Data Residency

* **Review comments processed locally** on your machine
* Model weights stored locally (`~/.ollama/models/`)
* No cloud synchronization or telemetry for LLM inference
* ⚠️ **Code already on GitHub** (required for PR workflow)

#### 3. No LLM Vendor Dependencies

* **Direct HTTP communication** with local Ollama server
* No LLM vendor intermediary services (OpenAI/Anthropic)
* No LLM vendor analytics or tracking
* ⚠️ **GitHub and CodeRabbit still involved** (required)

#### 4. User Control (LLM Models)

* **You control when models download** (explicit `ollama pull` required)
* **You control when models update** (no automatic updates)
* **You control model data deletion** (standard file system operations)

#### 5. Encryption at Rest (Optional)

* **Use encrypted filesystems** for model storage
* **Standard OS-level encryption** (LUKS, FileVault, BitLocker)
* **No special Ollama configuration required**

#### 6. Access Control

* **Standard OS permissions** apply to Ollama process and files
* **User-level isolation** via Unix permissions
* **Optional: Run in Docker** for additional containerization

### API Provider Considerations

When using API-based providers, understand the privacy limitations:

#### Data in Transit

* ✅ **Encrypted via TLS** (HTTPS)
* ⚠️ **Provider can decrypt** (they control the endpoint)
* ⚠️ **Vulnerable to MitM** (if certificate verification bypassed)

#### Data at Rest (Provider's Servers)

* ⚠️ **Temporary storage** for request processing
* ⚠️ **Retention period varies** (30-90 days typical)
* ⚠️ **Used for abuse monitoring** and potentially training
* ⚠️ **Subject to provider's security** (data breaches possible)

#### Third-Party Subprocessors

* ⚠️ **Providers may use subprocessors** (cloud hosting, monitoring)
* ⚠️ **Review provider's subprocessor list**
* ⚠️ **Additional parties may have access**

---

## Threat Model for Privacy

### Threats Mitigated by Local Operation (Ollama)

| Threat | Risk with API | Risk with Ollama |
| -------- | -------------- | ------------------ |
| **Data Breach at Provider** | High - All customer data exposed | None - No data at provider |
| **Unauthorized Access** | Medium - Provider employees, hackers | Low - OS-level controls |
| **Man-in-the-Middle Attack** | Medium - Network interception | None - Localhost only |
| **Data Retention Abuse** | High - Provider keeps data indefinitely | None - You control retention |
| **Regulatory Non-Compliance** | Medium-High - Depends on provider | Low - Simplified compliance |
| **Subpoena/Legal Disclosure** | High - Provider must comply | Low - Only you can be compelled |
| **Insider Threats (Provider)** | Medium - Malicious employees | None - Not applicable |
| **Supply Chain Attacks** | Medium - Compromised provider | Low - Limited attack surface |

### Threats NOT Mitigated by Local Operation

| Threat | Mitigation |
| -------- | ----------- |
| **Local Machine Compromise** | Strong endpoint security, EDR, regular patching |
| **Malicious Model Weights** | Download models from trusted sources only (official Ollama registry) |
| **Physical Access Attacks** | Encrypted storage, physical security controls |
| **Insider Threats (Your Org)** | Access controls, audit logging, separation of duties |
| **Code Injection via Review Comments** | Already mitigated by input validation in pr-resolve |

### Privacy Risk Assessment

**High Privacy Requirements** (Healthcare, Finance, Defense):

* ✅ **Recommended**: Ollama (local operation)
* ⚠️ **Acceptable with review**: API providers with BAA/DPA and compliance verification
* ❌ **Not recommended**: Free API tiers without enterprise agreements

**Medium Privacy Requirements** (Most Enterprises):

* ✅ **Recommended**: Ollama or Anthropic/OpenAI with enterprise agreements
* ✅ **Acceptable**: Claude CLI/Codex CLI with subscription

**Low Privacy Requirements** (Open Source, Public Code):

* ✅ **Recommended**: Any provider based on cost/performance trade-offs
* ✅ **Acceptable**: Free API tiers

---

## Security Controls for Local Models

While Ollama provides excellent privacy guarantees, follow these security best practices:

### 1. Model Provenance

**Risk**: Malicious or compromised model weights

**Controls**:

* ✅ Download models only from official Ollama registry
* ✅ Verify model checksums when available
* ✅ Use well-known, popular models (qwen2.5-coder, codellama)
* ❌ Avoid importing models from untrusted sources

### 2. Network Segmentation

**Risk**: Ollama server exposed to network

**Controls**:

* ✅ Default configuration binds to localhost only (127.0.0.1)
* ✅ Firewall rules to block external access
* ⚠️ If you need remote access, use VPN or SSH tunneling
* ❌ Do NOT expose Ollama directly to the internet

### 3. Access Control

**Risk**: Unauthorized access to Ollama service

**Controls**:

* ✅ Run Ollama under dedicated user account
* ✅ Restrict file permissions on `~/.ollama/` directory
* ✅ Use OS-level access controls (AppArmor, SELinux)
* ✅ Consider Docker containerization for additional isolation

### 4. Resource Limits

**Risk**: Denial of service via resource exhaustion

**Controls**:

* ✅ Set memory limits for Ollama process (Docker, systemd)
* ✅ Monitor resource usage (`ollama ps`, `htop`)
* ✅ Configure max concurrent requests if needed

### 5. Audit Logging

**Risk**: Unauthorized usage or configuration changes

**Controls**:

* ✅ Enable system logs for Ollama service (journalctl, syslog)
* ✅ Monitor Ollama logs for errors: `~/.ollama/logs/`
* ✅ Track model downloads and updates
* ✅ Integrate with SIEM if available

### 6. Encryption at Rest

**Risk**: Physical theft or unauthorized access to storage

**Controls**:

* ✅ Use full-disk encryption (LUKS, FileVault, BitLocker)
* ✅ Encrypt model storage directory specifically if needed
* ✅ Secure backup procedures for encrypted data

---

## Privacy Verification

### Automated Verification Script

Use the provided privacy verification script to confirm local-only operation:

```bash
# Run privacy verification test
./scripts/verify_privacy.sh

# Expected output
# ✅ Privacy Verification: PASSED
# ✅ No external network connections detected
# ✅ Report: privacy-verification-report.md

```

The script:

1. Monitors network traffic during Ollama inference
2. Verifies no connections to external IPs (for LLM inference only)
3. Generates detailed report with timestamps
4. Exit code 0 (success) or 1 (external connections detected)

**Note**: This script verifies Ollama's localhost-only operation. It does not prevent or monitor GitHub API calls, which are required for the tool to function.

See [Privacy Verification Script Documentation](local-llm-operation-guide.md#privacy-verification) for details.

### Manual Verification

You can also manually verify privacy using standard network monitoring tools:

#### Linux

```bash
# Monitor network connections while running inference
sudo tcpdump -i any port not 11434 and host not 127.0.0.1 &
pr-resolve apply 123 --llm-preset ollama-local
sudo pkill tcpdump

# Should see no packets captured (only localhost traffic)

```

#### macOS

```bash
# Monitor network connections
sudo lsof -i -n -P | grep -v "127.0.0.1"

# Run inference
pr-resolve apply 123 --llm-preset ollama-local

# Check lsof again - should see no new external connections

```

#### Docker Network Isolation

```bash
# Run Ollama in Docker with no external network
docker run -d --name ollama \
  --network none \
  -v ollama:/root/.ollama \
  ollama/ollama

# This will FAIL to download models (no network)
# But inference works fine after models are pre-loaded

```

---

## Related Documentation

### Privacy & Local LLM Operation

* [Local LLM Operation Guide](local-llm-operation-guide.md) - Local LLM setup with Ollama
* [Privacy FAQ](privacy-faq.md) - Common privacy questions answered
* [Ollama Setup Guide](ollama-setup.md) - Installation and configuration

### Security

* [Security Architecture](security-architecture.md) - Overall security design
* [API Key Security](llm-configuration.md#api-key-security) - Secure API key management

### Configuration

* [LLM Configuration Guide](llm-configuration.md) - Provider setup and presets
* [Configuration Guide](configuration.md) - General configuration options

### Performance

* [Performance Benchmarks](performance-benchmarks.md) - Provider performance comparison

---

## Conclusion

**Ollama reduces third-party exposure** by keeping LLM inference local to your machine. This architecture:

✅ **Eliminates LLM vendor exposure** - OpenAI/Anthropic never see your review comments
✅ **Simplifies compliance** - One fewer data processor (no LLM vendor BAA/DPA)
✅ **Reduces attack surface** - Fewer third parties with access
✅ **Gives you control over LLM** - Local model management
✅ **Costs nothing for LLM** - Free after initial hardware investment

⚠️ **Important limitations**:

* ❌ **Not air-gapped** - Requires internet to fetch PR comments from GitHub
* ⚠️ **GitHub has access** - Your code is on GitHub (required for PR workflow)
* ⚠️ **CodeRabbit has access** - Review bot processes your code (required)

**When to use Ollama**:

* Want to minimize third-party LLM vendor exposure
* Regulated industries wanting to reduce data processor chain (GDPR, HIPAA, SOC2)
* Cost-conscious usage (no per-request LLM fees)
* Organizations with policies against cloud LLM services

**When API providers may be acceptable**:

* Open source / public code
* Enterprise agreements with BAA/DPA already in place
* Need for highest quality models (GPT-4, Claude Sonnet 4.5)
* Budget available for per-request costs
* Comfortable with additional third-party exposure

**The honest trade-off**: Ollama eliminates LLM vendor exposure at the cost of local hardware requirements and potentially lower model quality. Your code is still on GitHub and accessible to CodeRabbit—Ollama just prevents one additional third party (the LLM vendor) from accessing your review comments.

For step-by-step local LLM setup, see the [Local LLM Operation Guide](local-llm-operation-guide.md).
