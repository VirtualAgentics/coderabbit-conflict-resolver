# Privacy FAQ

Frequently asked questions about privacy, data handling, local LLM operation, and compliance when using Review Bot Automator with LLM providers.

> **See Also**: [Privacy Architecture](privacy-architecture.md) for detailed privacy analysis and [Local LLM Operation Guide](local-llm-operation-guide.md) for setup instructions.

## Table of Contents

* [Privacy & Data Handling](#privacy--data-handling)
* [Local LLM Operation](#local-llm-operation)
* [Compliance & Regulations](#compliance--regulations)
* [Security & Verification](#security--verification)
* [Model Management & Updates](#model-management--updates)
* [Performance & Cost](#performance--cost)

---

## Privacy & Data Handling

### Q: Who has access to my code when using this tool?

**A: GitHub and CodeRabbit always have access (required for PR workflow).** The privacy difference with Ollama is whether an LLM vendor (OpenAI/Anthropic) also gets access.

**With API Providers (OpenAI/Anthropic)**:

* ✅ GitHub (has access - your code is hosted here)
* ✅ CodeRabbit (has access - generates review comments)
* ❌ OpenAI/Anthropic (has access - processes review comments)

**With Ollama (Local LLM)**:

* ✅ GitHub (has access - your code is hosted here)
* ✅ CodeRabbit (has access - generates review comments)
* ✅ Local LLM (localhost only - no third-party vendor)

**Bottom line**: Ollama prevents one additional third party (LLM vendor) from seeing your review comments, but your code is still on GitHub.

### Q: Does Ollama send any data to the internet?

**A: No, Ollama processes everything locally.** All LLM inference happens via localhost (`127.0.0.1:11434`). Review comments never go to OpenAI/Anthropic.

**However**, the tool still needs internet to:

* Fetch PR comments from GitHub API
* Push resolved changes back to GitHub

You can verify Ollama's localhost-only operation:

```bash
./scripts/verify_privacy.sh

```

### Q: What data do API-based providers (OpenAI, Anthropic) receive?

**A**: When using API providers, the following data is transmitted to their servers:

* Review comments from GitHub
* Relevant code context for parsing
* File paths and line numbers
* Model configuration (model name, max tokens, etc.)

**Not sent**:

* Your full repository
* Unrelated files
* Git history
* Your GitHub token (only used locally)

**Reality check**: Your code is already on GitHub, so the main privacy concern is whether the LLM vendor (OpenAI/Anthropic) also sees your review comments.

See [Privacy Architecture - Data Flow Comparison](privacy-architecture.md#data-flow-comparison) for detailed diagrams.

### Q: Do API providers use my code to train their models?

**A**: It depends on the provider and your agreement:

* **OpenAI**: By default, API data is retained for 30 days for abuse monitoring. You can opt out of training data usage. See [OpenAI's API data usage policy](<https://openai.com/policies/api-data-usage-policies>).

* **Anthropic**: API requests are NOT used for training by default. Data is retained for 90 days for Trust & Safety. See [Anthropic's commercial terms](<https://www.anthropic.com/legal/commercial-terms>).

* **Ollama**: No data sent to any vendor. Not applicable.

**Recommendation**: For proprietary code, use Ollama to eliminate LLM vendor exposure, or sign enterprise agreements with opt-out clauses.

### Q: Can I use this with proprietary/confidential code?

**A**: Yes, but understand the limitations:

**Reality Check First**:

* ⚠️ Your code is on GitHub (required for PR workflow)
* ⚠️ CodeRabbit processes your code (required for reviews)

**Using Ollama**:

* ✅ **Reduces exposure** - Eliminates LLM vendor from access chain
* ✅ **No LLM vendor data retention** - You control local data
* ⚠️ **GitHub/CodeRabbit still have access** - Cannot be avoided

**Using API Providers**:

* ⚠️ **Adds LLM vendor to chain** - OpenAI/Anthropic also gets access
* ⚠️ **Check your company's policies** - Some prohibit cloud LLM usage
* ⚠️ **Review provider's data policies** - Understand retention and training policies
* ⚠️ **Consider enterprise agreements** - Business Associate Agreements (BAA), Data Processing Agreements (DPA)

### Q: What about API keys? Are they secure?

**A**: API keys for cloud providers (OpenAI, Anthropic) are:

* ✅ **Never logged** by Review Bot Automator
* ✅ **Never sent to GitHub** or other services
* ✅ **Only sent to the respective LLM provider** (OpenAI/Anthropic)
* ✅ **Stored in environment variables or config files** (user-controlled)

**Best practices**:

```bash
# Use environment variables (recommended)
export CR_LLM_API_KEY="sk-..."

# Or use config file with interpolation
# config.yaml
llm:
  api_key: ${ANTHROPIC_API_KEY}  # References env var

# Never commit API keys to Git

```

See [LLM Configuration - API Key Security](llm-configuration.md#api-key-security) for details.

### Q: Does Review Bot Automator collect any telemetry or analytics?

**A**: **No**. Review Bot Automator collects zero telemetry, analytics, or usage data. Everything runs locally on your machine.

We do not:

* ❌ Phone home
* ❌ Track usage
* ❌ Collect metrics
* ❌ Send crash reports (unless you manually report issues on GitHub)

Your privacy is paramount.

### Q: Can I audit what data is being sent?

**A**: Yes! Several ways to verify:

**1. Network Monitoring**:

```bash
# Linux: Monitor all HTTP requests
sudo tcpdump -i any -A 'tcp port 80 or tcp port 443' | grep -i "POST\|GET"

# macOS: Use lsof
lsof -i -n -P | grep python

```

**2. Privacy Verification Script** (for Ollama):

```bash
./scripts/verify_privacy.sh  # Verifies localhost-only LLM operation

```

**3. Code Inspection**:

* Review Bot Automator is **open source** - review the code on GitHub
* LLM provider integrations: `src/review_bot_automator/llm/providers/`

**4. Debug Logging**:

```bash
# Enable debug logging to see all LLM requests
export CR_LOG_LEVEL=DEBUG
pr-resolve apply 123 --llm-preset ollama-local 2>&1 | less

```

---

## Local LLM Operation

### Q: Can I use this without an internet connection?

**A: No.** This tool requires internet access to function.

**Why Internet is Required**:

* ❌ Must fetch PR comments from GitHub API
* ❌ Must push resolved changes back to GitHub
* ❌ Your code is already on GitHub (PR workflow requirement)

**What Ollama Actually Does**:

* ✅ Processes review comments locally (no LLM vendor)
* ✅ Eliminates OpenAI/Anthropic from access chain
* ⚠️ **Does NOT enable offline operation** - GitHub API still required

See [Local LLM Operation Guide](local-llm-operation-guide.md) for honest explanation of what local LLM means.

### Q: Can I use this in an air-gapped environment (no network at all)?

**A: No.** Air-gapped operation is fundamentally incompatible with this tool's design.

**Why Air-Gapped Won't Work**:

1. Tool must fetch PR comments from GitHub API (requires internet)
2. Tool must push changes back to GitHub (requires internet)
3. By the time CodeRabbit review comments exist, code is already on GitHub
4. CodeRabbit itself requires internet to generate reviews

**Reality**: If you need air-gapped code review, this tool is not the right solution. Consider:

* Local code review tools (not AI-powered)
* Self-hosted GitLab/Gitea with local LLM integration
* Manual code reviews without automated tools

### Q: What needs to be downloaded in advance for local LLM use?

**A**: Before using local LLM with Ollama, download:

**Required**:

* Ollama installer (one-time)
* At least one LLM model (e.g., `ollama pull qwen2.5-coder:7b`)
* Review Bot Automator Python package and dependencies
* Python 3.12+ runtime

**Important**: These downloads enable local LLM processing, but the tool still requires internet to fetch PR data from GitHub.

**Total disk space**: ~10-20GB depending on models.

### Q: Will it still work if I disconnect my network mid-operation?

**A: No.** If you disconnect during operation, GitHub API calls will fail.

**What Happens**:

1. **Fetching PR data** (requires internet) - Tool downloads review comments from GitHub
2. **LLM inference** (works with network disconnected) - Ollama processes locally
3. **Pushing changes** (requires internet) - Tool pushes fixes back to GitHub

**Bottom line**: You need internet connectivity for the full workflow. Disconnecting mid-operation will cause failures.

### Q: What's the actual privacy benefit of using Ollama?

**A: Eliminating LLM vendor exposure.** That's it.

**Before (API Providers)**:

* GitHub sees your code ✓
* CodeRabbit sees your code ✓
* OpenAI/Anthropic sees review comments ✓

**After (Ollama)**:

* GitHub sees your code ✓
* CodeRabbit sees your code ✓
* LLM vendor sees review comments ✗ (eliminated)

**Honest assessment**: This reduces third-party exposure by one entity (the LLM vendor). It does NOT achieve:

* ❌ Air-gapped operation
* ❌ Offline operation
* ❌ Complete data isolation
* ❌ Zero third-party access

**It DOES achieve**:

* ✅ No LLM vendor seeing your review comments
* ✅ One fewer data processor in compliance chain
* ✅ Reduced attack surface (one fewer third party)
* ✅ No LLM vendor data retention concerns

### Q: How do I verify I'm operating with localhost-only LLM?

**A**: Use the privacy verification script:

```bash
./scripts/verify_privacy.sh

```

**What This Verifies**:

* ✅ Ollama only communicates on localhost (127.0.0.1:11434)
* ✅ No connections to OpenAI or Anthropic
* ⚠️ GitHub API calls are expected (required for tool to function)

**What This Does NOT Verify**:

* ❌ Offline operation (not possible)
* ❌ Air-gapped operation (not possible)
* ❌ Zero internet usage (GitHub API required)

---

## Compliance & Regulations

### Q: Is this GDPR-compliant for handling European user data?

**A**: **It helps, but doesn't solve everything.**

**Reality for All Configurations**:

* ⚠️ Code is on GitHub (US-based company)
* ⚠️ CodeRabbit processes code (data processor)
* ⚠️ Data Processing Agreements needed for GitHub/CodeRabbit

**Using Ollama - Additional Benefits**:

* ✅ **Reduces processors** - One fewer data processor (no LLM vendor)
* ✅ **Simplifies DPA chain** - No additional agreement for LLM vendor
* ✅ **Reduces cross-border transfers** - LLM processing stays local

**Using API Providers - Additional Considerations**:

* ⚠️ **Adds another processor** - OpenAI/Anthropic to DPA chain
* ⚠️ **Additional cross-border transfer** - Review comments to US-based LLM vendor
* ⚠️ **Requires LLM vendor DPA** - Additional legal agreement needed

See [Privacy Architecture - GDPR Compliance](privacy-architecture.md#gdpr-general-data-protection-regulation).

### Q: Can I use this for HIPAA-regulated healthcare code?

**A**: **Carefully, and with proper agreements.**

**Reality for All Configurations**:

* ⚠️ If PHI in code, it's already on GitHub (BAA required with GitHub)
* ⚠️ CodeRabbit processes code (BAA required with CodeRabbit)
* ⚠️ Review your organization's policies on cloud code hosting

**Using Ollama - Additional Benefits**:

* ✅ **Reduces BAA requirements** - No additional BAA for LLM vendor
* ✅ **Simpler compliance chain** - One fewer business associate

**Using API Providers - Additional Considerations**:

* ⚠️ **Another BAA required** - Must sign BAA with OpenAI/Anthropic
* ⚠️ **Check HIPAA-eligible services** - Not all API tiers support HIPAA
* ⚠️ **Additional costs** - HIPAA-compliant tiers often more expensive
* ❌ **Verify current HIPAA support** - OpenAI/Anthropic support varies

**Important**: Using Ollama does NOT eliminate HIPAA concerns if your code contains PHI and is hosted on GitHub. It only reduces the number of business associates.

See [Privacy Architecture - HIPAA Compliance](privacy-architecture.md#hipaa-health-insurance-portability-and-accountability-act).

### Q: What about SOC 2 compliance?

**A**: **Ollama reduces vendor assessment burden.**

**Reality for All Configurations**:

* ⚠️ GitHub vendor assessment required
* ⚠️ CodeRabbit vendor assessment required

**Using Ollama - Benefits**:

* ✅ **One fewer vendor** - No LLM vendor assessment needed
* ✅ **Simpler SOC 2 scope** - LLM processing under your control

**Using API Providers - Additional Burden**:

* ⚠️ **Another vendor assessment** - OpenAI/Anthropic SOC 2 review needed
* ⚠️ **SOC 2 reports must be reviewed** - Ensure Type II reports available
* ⚠️ **Continuous monitoring** - Provider's compliance status may change

See [Privacy Architecture - SOC 2 Compliance](privacy-architecture.md#soc-2-service-organization-control).

### Q: Can I use this in defense/government environments?

**A**: **With significant caveats.**

**Reality Check**:

* ❌ Code is on GitHub (public cloud platform)
* ❌ CodeRabbit processes code (third-party service)
* ❌ Not suitable for classified environments

**For Unclassified/CUI Environments**:

* ⚠️ Check with your security officer about GitHub usage
* ⚠️ Ollama reduces third-party exposure (no LLM vendor)
* ⚠️ Still requires internet connectivity (GitHub API)

**For Classified Environments**:

* ❌ This tool is **NOT appropriate**
* ❌ Cannot be used in air-gapped/SCIF environments
* ❌ Use local, non-cloud-based code review tools instead

---

## Security & Verification

### Q: How do I know Ollama isn't secretly sending data somewhere?

**A**: Multiple verification mechanisms:

**1. Privacy Verification Script**:

```bash
./scripts/verify_privacy.sh

```

Generates detailed report showing network traffic during Ollama inference.

**2. Open Source**:

* Ollama is open source: <https://github.com/ollama/ollama>
* Review the code yourself
* Community-audited

**3. Network Monitoring**:

```bash
# Linux: Monitor connections during inference
sudo lsof -i -n -P | grep ollama

# macOS
lsof -i -n -P | grep ollama

# Should ONLY show localhost:11434

```

**4. Default Configuration**:

* Ollama binds to localhost (127.0.0.1) by default
* No external network access unless explicitly configured

### Q: What if Ollama models are compromised?

**A**: Download models only from trusted sources:

✅ **Official Ollama registry**: <https://ollama.ai/library>
✅ **Popular, well-known models**: qwen2.5-coder, codellama, etc.
❌ **Avoid untrusted imports**: Don't import random model files

**Verification**:

```bash
# Only pull from official registry
ollama pull qwen2.5-coder:7b  # Safe

# Don't do this with untrusted files
ollama import /tmp/suspicious-model.gguf  # Risky

```

### Q: Should I firewall Ollama?

**A**: Yes, recommended:

```bash
# Ensure Ollama only binds to localhost (default)
# Check Ollama is NOT exposed
sudo lsof -i :11434

# Should show: 127.0.0.1:11434 (localhost only)

# Optional: Explicit firewall rule
sudo ufw deny 11434  # Block external access (Linux)

```

**Never expose Ollama to the internet** without authentication/TLS.

---

## Model Management & Updates

### Q: How often do I need to update models?

**A**: Models don't need frequent updates:

* **Models are static** - Unlike cloud APIs, local models don't change unless you update them
* **Update when**: New model versions released with better quality
* **Check releases**: Follow Ollama blog or model pages

```bash
# Update model to latest version
ollama pull qwen2.5-coder:7b

# Old version is replaced automatically

```

### Q: Can I use custom/fine-tuned models?

**A**: Yes, Ollama supports custom models:

```bash
# Import custom model
ollama import ./my-model.gguf --name my-custom-model

# Use in config
llm:
  provider: ollama
  model: my-custom-model

```

**Privacy note**: Ensure custom models come from trusted sources.

### Q: How much disk space do models need?

**A**: Varies by model size:

* **3B models**: ~2-4GB
* **7B models**: ~4-8GB
* **13B models**: ~8-16GB
* **70B+ models**: ~40GB+

```bash
# Check model sizes
ollama list

# Remove unused models
ollama rm codellama:7b

```

---

## Performance & Cost

### Q: Is Ollama slower than API providers?

**A**: Depends on your hardware:

**With GPU** (NVIDIA/AMD/Apple Silicon):

* Similar latency to API providers
* Often faster for small prompts (no network overhead)

**CPU Only**:

* Significantly slower (10-60 seconds per inference)
* Acceptable for small PR reviews
* Consider smaller models (3B) for speed

**Recommendation**: Use API providers if you need speed and don't have GPU. Use Ollama if privacy/cost more important than speed.

### Q: What's the cost comparison?

**A**: Total cost of ownership:

**Ollama (Local)**:

* Hardware: $0 (use existing) to $2000+ (dedicated GPU server)
* Electricity: $5-20/month (GPU usage)
* LLM costs: $0
* **Ongoing**: $0-20/month

**OpenAI API**:

* Hardware: $0
* Per-PR cost: ~$0.01-0.05
* 1000 PRs/month: ~$10-50/month
* **Ongoing**: $10-50+/month (scales with usage)

**Anthropic API**:

* Hardware: $0
* Per-PR cost: ~$0.05-0.15
* 1000 PRs/month: ~$50-150/month
* **Ongoing**: $50-150+/month (scales with usage)

**Break-even**: If processing >500 PRs/month, Ollama becomes cost-effective despite hardware investment.

### Q: Can I mix local and API providers?

**A**: Yes! Use presets for different scenarios:

```yaml
# config.yaml
llm:
  enabled: true

  # Default: Ollama for privacy
  provider: ollama
  model: qwen2.5-coder:7b

  # Presets for different use cases
  presets:
    local:
      provider: ollama
      model: qwen2.5-coder:7b

    fast-api:
      provider: openai
      model: gpt-4
      api_key: ${OPENAI_API_KEY}

    high-quality:
      provider: anthropic
      model: claude-sonnet-4.5
      api_key: ${ANTHROPIC_API_KEY}

```

Use with:

```bash
# Privacy-sensitive PR: use local
pr-resolve apply 123 --llm-preset local

# Open-source PR: use fast API
pr-resolve apply 456 --llm-preset fast-api

```

---

## Related Documentation

### Setup & Configuration

* [Local LLM Operation Guide](local-llm-operation-guide.md) - Complete local LLM setup
* [Ollama Setup Guide](ollama-setup.md) - Detailed Ollama installation
* [LLM Configuration Guide](llm-configuration.md) - Provider setup and presets

### Privacy & Security

* [Privacy Architecture](privacy-architecture.md) - Comprehensive privacy analysis
* [Security Architecture](security-architecture.md) - Overall security design

### Performance

* [Performance Benchmarks](performance-benchmarks.md) - Provider performance comparison

---

**Have more questions?** Open an issue on [GitHub](https://github.com/VirtualAgentics/review-bot-automator/issues) or check the [Privacy Architecture](privacy-architecture.md) for detailed analysis.
