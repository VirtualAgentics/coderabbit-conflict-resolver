# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Command-line interface for review-bot-automator."""

import hashlib
import logging
import re
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from review_bot_automator import __version__
from review_bot_automator.cli.config_loader import load_runtime_config
from review_bot_automator.cli.llm_error_handler import handle_llm_errors
from review_bot_automator.config.presets import PresetConfig
from review_bot_automator.config.runtime_config import (
    ApplicationMode,
    RuntimeConfig,
)
from review_bot_automator.core.resolver import ConflictResolver
from review_bot_automator.llm.base import LLMParser
from review_bot_automator.llm.cost_tracker import CostTracker
from review_bot_automator.llm.exceptions import LLMError
from review_bot_automator.llm.metrics import LLMMetrics
from review_bot_automator.llm.metrics_aggregator import MetricsAggregator
from review_bot_automator.llm.parallel_parser import ParallelLLMParser
from review_bot_automator.llm.parser import UniversalLLMParser
from review_bot_automator.llm.presets import LLMPresetConfig

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Create the main Click command-line interface for the Review Bot Automator.

    Defines the top-level `cli` command group with a version option and registers the
    `analyze`, `apply`, and `simulate` subcommands; configures the Rich console used
    for styled terminal output.
    """


MAX_GITHUB_USERNAME_LENGTH = 39
MAX_GITHUB_REPO_LENGTH = 100


# Compiled pattern for detecting control characters only.
_INJECTION_PATTERN = re.compile(r"[\x00-\x1f\x7f]")  # Control chars only


def _create_llm_parser(
    runtime_config: RuntimeConfig,
) -> tuple[LLMParser | None, CostTracker | None]:
    """Create LLM parser from runtime configuration.

    Creates either ParallelLLMParser or UniversalLLMParser based on configuration.
    Returns None if LLM is disabled or initialization fails.

    Args:
        runtime_config: Runtime configuration containing LLM settings.

    Returns:
        Tuple of (LLMParser instance, CostTracker instance), or (None, None) if
        LLM is disabled or initialization fails. CostTracker is only created if
        a cost budget is configured.
    """
    if not runtime_config.llm_enabled:
        return None, None

    try:
        from review_bot_automator.llm.factory import create_provider

        # Create provider from RuntimeConfig
        provider = create_provider(
            provider=runtime_config.llm_provider,
            model=runtime_config.llm_model,
            api_key=runtime_config.llm_api_key,
        )

        # Create cost tracker if budget is configured
        cost_tracker: CostTracker | None = None
        if runtime_config.llm_cost_budget is not None:
            cost_tracker = CostTracker(budget=runtime_config.llm_cost_budget)
            logger.info(f"Cost budget: ${runtime_config.llm_cost_budget:.4f}")

        # Create parser with provider (use ParallelLLMParser if parallel parsing enabled)
        llm_parser: LLMParser
        if runtime_config.llm_parallel_parsing:
            llm_parser = ParallelLLMParser(
                provider=provider,
                max_workers=runtime_config.llm_parallel_max_workers,
                rate_limit=runtime_config.llm_rate_limit,
                fallback_to_regex=runtime_config.llm_fallback_to_regex,
                confidence_threshold=runtime_config.llm_confidence_threshold,
                max_tokens=runtime_config.llm_max_tokens,
                cost_tracker=cost_tracker,
            )
            console.print(
                f"[dim]✓ Parallel LLM parser initialized: "
                f"{runtime_config.llm_provider} ({runtime_config.llm_model}, "
                f"{runtime_config.llm_parallel_max_workers} workers, "
                f"{runtime_config.llm_rate_limit} req/s)[/dim]"
            )
        else:
            llm_parser = UniversalLLMParser(
                provider=provider,
                fallback_to_regex=runtime_config.llm_fallback_to_regex,
                confidence_threshold=runtime_config.llm_confidence_threshold,
                max_tokens=runtime_config.llm_max_tokens,
                cost_tracker=cost_tracker,
            )
            console.print(
                f"[dim]✓ LLM parser initialized: {runtime_config.llm_provider} "
                f"({runtime_config.llm_model})[/dim]"
            )

        return llm_parser, cost_tracker

    except Exception as e:
        logger.exception("Failed to initialize LLM parser")
        console.print(f"[yellow]⚠ Warning: Failed to initialize LLM parser: {e}[/yellow]")
        console.print("[dim]Falling back to regex-only parsing[/dim]")
        return None, None


def sanitize_for_output(value: str) -> str:
    """Redact control characters before printing.

    Detects control characters (null bytes, line breaks, etc.) and returns
    a redacted placeholder if any are present. Logs safe metadata (length and
    hash) at debug level for troubleshooting without exposing the original value.

    Note: This function does NOT remove visible shell metacharacters (;, |, $, etc.).
    Only control characters are detected and trigger redaction.

    Args:
        value (str): The string to sanitize for terminal output.

    Returns:
        str: "[REDACTED]" if control characters are found; otherwise the original string.
    """
    if _INJECTION_PATTERN.search(value):
        # Compute SHA-256 hash to avoid logging sensitive content
        value_bytes = value.encode("utf-8")
        value_hash = hashlib.sha256(value_bytes).hexdigest()
        logger.debug(
            "Redacting value containing control characters: length=%d, hash=%s",
            len(value),
            value_hash,
        )
        return "[REDACTED]"
    return value


def validate_github_username(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """Validate GitHub username for safety.

    Enforces GitHub username rules: A-Za-z0-9 and hyphen only, 1-39 chars,
    cannot start/end with hyphen, no consecutive hyphens.

    Args:
        ctx: Click context object.
        param: Click parameter object.
        value: Username value to validate.

    Returns:
        str: The validated username.

    Raises:
        click.BadParameter: If username validation fails.
    """
    # Basic type/emptiness checks
    if not isinstance(value, str) or not value.strip():
        raise click.BadParameter("username required", param=param, ctx=ctx)

    # Enforce GitHub username length (1-39 characters)
    if len(value) > MAX_GITHUB_USERNAME_LENGTH:
        raise click.BadParameter(
            f"username too long (max {MAX_GITHUB_USERNAME_LENGTH})", param=param, ctx=ctx
        )

    # Disallow slashes and whitespace
    if "/" in value or "\\" in value or any(ch.isspace() for ch in value):
        raise click.BadParameter(
            "username must be a single segment (no slashes or spaces)", param=param, ctx=ctx
        )

    # GitHub username rules: A-Za-z0-9 and hyphen only, no leading/trailing hyphen
    # Regex: starts with alphanum, can have hyphens not at start/end, no consecutive hyphens
    if not re.fullmatch(r"^[A-Za-z0-9]([A-Za-z0-9]|-(?=[A-Za-z0-9]))*$", value):
        raise click.BadParameter(
            "username contains invalid characters or format; "
            "allowed: A-Za-z0-9 and hyphen, cannot start/end with hyphen, "
            "no consecutive hyphens",
            param=param,
            ctx=ctx,
        )
    return value


def validate_github_repo(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """Validate GitHub repository name for safety.

    Enforces length and character constraints for repository names:
    letters, digits, dot, underscore, hyphen. Max 100 characters.

    Args:
        ctx: Click context object.
        param: Click parameter object.
        value: Repository name to validate.

    Returns:
        str: The validated repository name.

    Raises:
        click.BadParameter: If repository name validation fails.
    """
    # Basic type/emptiness checks
    if not isinstance(value, str) or not value.strip():
        raise click.BadParameter("repository name required", param=param, ctx=ctx)

    # Enforce repository name length (max 100 characters)
    if len(value) > MAX_GITHUB_REPO_LENGTH:
        raise click.BadParameter(
            f"repository name too long (max {MAX_GITHUB_REPO_LENGTH})", param=param, ctx=ctx
        )

    # Disallow slashes and whitespace
    if "/" in value or "\\" in value or any(ch.isspace() for ch in value):
        raise click.BadParameter(
            "identifier must be a single segment (no slashes or spaces)",
            param=param,
            ctx=ctx,
        )

    # Allowed characters: letters, digits, dot, underscore, hyphen
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise click.BadParameter(
            "repository name contains invalid characters; "
            "allowed: letters, digits, dot, underscore, hyphen",
            param=param,
            ctx=ctx,
        )

    # Reject reserved names
    if value in (".", ".."):
        raise click.BadParameter("repository name cannot be '.' or '..'", param=param, ctx=ctx)

    # Reject names ending with .git (case-insensitive)
    if value.lower().endswith(".git"):
        raise click.BadParameter("repository name cannot end with '.git'", param=param, ctx=ctx)

    return value


def validate_pr_number(ctx: click.Context, param: click.Parameter, value: int) -> int:
    """Validate that PR number is positive.

    Args:
        ctx: Click context.
        param: Parameter being validated.
        value: The PR number to validate.

    Returns:
        int: The validated PR number.

    Raises:
        click.BadParameter: If PR number is less than 1.
    """
    if value < 1:
        raise click.BadParameter(
            "PR number must be positive (>= 1)",
            ctx=ctx,
            param=param,
        )
    return value


def validate_cost_budget(
    ctx: click.Context, param: click.Parameter, value: float | None
) -> float | None:
    """Validate that cost budget is non-negative.

    Args:
        ctx: Click context.
        param: Parameter being validated.
        value: The cost budget to validate (None for unlimited).

    Returns:
        The validated cost budget or None.

    Raises:
        click.BadParameter: If cost budget is negative.
    """
    if value is not None and value < 0:
        raise click.BadParameter(
            "cost budget must be non-negative",
            ctx=ctx,
            param=param,
        )
    if value == 0.0:
        click.echo(
            "Warning: --cost-budget=0 will disable all LLM parsing "
            "(budget exhausted immediately)",
            err=True,
        )
    return value


def _display_llm_metrics(metrics: LLMMetrics) -> None:
    """Display LLM metrics in a formatted panel with table.

    Shows token usage, costs, cache performance, and parsing statistics
    in a user-friendly format using Rich Panel and Table.

    Args:
        metrics: LLM metrics to display.

    Example output:
        ╭─ LLM Metrics (Anthropic claude-haiku-4) ─────────────────╮
        │ Changes parsed: 20 | Avg confidence: 92.0%              │
        │ API calls: 7 | Total tokens: 15,420                     │
        │ Cache hit rate: 65.0% | Total cost: $0.0234             │
        │ Cost per change: $0.0012 | Avg tokens/call: 2,203       │
        ╰───────────────────────────────────────────────────────────╯
    """
    # Build metrics table
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", justify="left")
    table.add_column(style="white", justify="left")

    # Row 1: Changes and confidence
    table.add_row(
        f"Changes parsed: {metrics.changes_parsed}",
        f"Avg confidence: {metrics.avg_confidence * 100:.1f}%",
    )

    # Row 2: API calls and tokens
    table.add_row(
        f"API calls: {metrics.api_calls}",
        f"Total tokens: {metrics.total_tokens:,}",
    )

    # Row 3: Cache and cost
    cache_display = f"{metrics.cache_hit_rate * 100:.1f}%"
    cost_display = f"${metrics.total_cost:.4f}" if metrics.total_cost > 0 else "Free"
    table.add_row(
        f"Cache hit rate: {cache_display}",
        f"Total cost: {cost_display}",
    )

    # Row 4: Computed metrics
    cost_per_change_display = (
        f"${metrics.cost_per_change:.4f}" if metrics.cost_per_change > 0 else "Free"
    )
    table.add_row(
        f"Cost per change: {cost_per_change_display}",
        f"Avg tokens/call: {metrics.avg_tokens_per_call:,.0f}",
    )

    # Row 5: GPU info (Ollama only)
    if metrics.gpu_info is not None:
        if metrics.gpu_info.available:
            gpu_model = f"{metrics.gpu_info.gpu_type}"
            if metrics.gpu_info.model_name:
                gpu_model += f" {metrics.gpu_info.model_name}"
            if metrics.gpu_info.vram_total_mb:
                gpu_model += f" ({metrics.gpu_info.vram_total_mb // 1024}GB)"
            table.add_row(f"Hardware: {gpu_model}", "")
        else:
            table.add_row("Hardware: CPU (No GPU detected)", "")

    # Display in panel
    # Capitalize provider name (OpenAI special case)
    provider_display = (
        "OpenAI" if metrics.provider.lower() == "openai" else metrics.provider.capitalize()
    )
    title = f"LLM Metrics ({provider_display} {metrics.model})"

    panel = Panel(
        table,
        title=title,
        border_style="green",
        padding=(1, 2),
    )

    console.print()
    console.print(panel)


def _display_aggregated_metrics(aggregator: MetricsAggregator) -> None:
    """Display detailed aggregated metrics with latency percentiles.

    Shows comprehensive metrics including per-provider breakdown and
    latency percentiles (p50, p95, p99) in a formatted Rich panel.

    Args:
        aggregator: MetricsAggregator with collected request metrics.
    """
    metrics = aggregator.get_aggregated_metrics()

    if metrics.total_requests == 0:
        console.print("[dim]No LLM requests recorded[/dim]")
        return

    # Build metrics table
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", justify="left")
    table.add_column(style="white", justify="left")

    # Row 1: Request counts
    table.add_row(
        f"Total requests: {metrics.total_requests}",
        f"Success rate: {metrics.success_rate * 100:.1f}%",
    )

    # Row 2: Latency percentiles
    table.add_row(
        f"Latency p50: {metrics.latency_p50 * 1000:.0f}ms",
        f"p95: {metrics.latency_p95 * 1000:.0f}ms / p99: {metrics.latency_p99 * 1000:.0f}ms",
    )

    # Row 3: Cost and cache
    cost_display = f"${metrics.total_cost:.4f}" if metrics.total_cost > 0 else "Free"
    table.add_row(
        f"Total cost: {cost_display}",
        f"Cache hit rate: {metrics.cache_hit_rate * 100:.1f}%",
    )

    # Row 4: Cache savings
    if metrics.cache_savings > 0:
        table.add_row(
            f"Cache savings: ${metrics.cache_savings:.4f}",
            "",
        )

    # Per-provider breakdown
    if metrics.provider_stats:
        table.add_row("", "")
        table.add_row("[bold]Per-provider breakdown:[/bold]", "")
        for name, stats in metrics.provider_stats.items():
            provider_display = "OpenAI" if name.lower() == "openai" else name.capitalize()
            table.add_row(
                f"  {provider_display}:",
                f"{stats.total_requests} reqs, p95={stats.latency_p95 * 1000:.0f}ms, "
                f"${stats.total_cost:.4f}",
            )

    # Display in panel
    panel = Panel(
        table,
        title="Aggregated LLM Metrics",
        border_style="blue",
        padding=(1, 2),
    )

    console.print()
    console.print(panel)


def _export_metrics(
    aggregator: MetricsAggregator,
    output_path: str,
    detail_level: str,
) -> None:
    """Export metrics to file (JSON or CSV).

    Args:
        aggregator: MetricsAggregator with collected request metrics.
        output_path: Path to output file (extension determines format).
        detail_level: 'summary' or 'full' (includes per-request data).
    """
    path = Path(output_path)
    suffix = path.suffix.lower()

    try:
        if suffix == ".csv":
            aggregator.export_csv(path)
            console.print(f"[green]✓ Metrics exported to {path}[/green]")
        elif suffix == ".json":
            include_requests = detail_level == "full"
            aggregator.export_json(path, include_requests=include_requests)
            console.print(f"[green]✓ Metrics exported to {path}[/green]")
        else:
            # Default to JSON
            include_requests = detail_level == "full"
            aggregator.export_json(path.with_suffix(".json"), include_requests=include_requests)
            console.print(f"[green]✓ Metrics exported to {path.with_suffix('.json')}[/green]")
    except OSError as e:
        console.print(f"[red]❌ Failed to export metrics: {e}[/red]")
        logger.error("Failed to export metrics to %s: %s", path, e)


def _display_cost_status(cost_tracker: CostTracker | None) -> None:
    """Display cost budget status panel.

    Shows cost budget utilization with color-coded status based on
    the tracker's configured warning threshold:
    - Green: Under warning threshold (OK)
    - Yellow: At/above warning threshold, under 100% (WARNING)
    - Red: 100%+ (EXCEEDED)

    Args:
        cost_tracker: CostTracker instance to display status for.
            Does nothing if tracker is None or has no budget set.
    """
    if cost_tracker is None or cost_tracker.budget is None:
        return  # No budget set, nothing to display

    utilization = cost_tracker.budget_utilization
    budget = cost_tracker.budget
    warning_threshold = cost_tracker.warning_threshold

    if utilization >= 1.0:
        style = "red"
        status = "EXCEEDED"
    elif utilization >= warning_threshold:
        style = "yellow"
        status = "WARNING"
    else:
        style = "green"
        status = "OK"

    console.print(
        f"[{style}]Cost: ${cost_tracker.accumulated_cost:.4f} / "
        f"${budget:.4f} ({utilization*100:.1f}%) - {status}[/{style}]"
    )


def _record_and_display_metrics(
    llm_metrics: LLMMetrics,
    owner: str,
    repo: str,
    pr: int,
    metrics_output: str | None,
    metrics_detail: str,
) -> None:
    """Record LLM metrics and display/export aggregated results.

    Creates a MetricsAggregator, records a synthetic request from LLMMetrics,
    displays the aggregated metrics, and optionally exports to file.

    Note: This records a single synthetic request from aggregated LLMMetrics.
    Per-request latency tracking requires direct provider integration with
    the MetricsAggregator.

    Args:
        llm_metrics: Aggregated LLM metrics from parsing.
        owner: Repository owner.
        repo: Repository name.
        pr: Pull request number.
        metrics_output: Optional file path for metrics export.
        metrics_detail: Detail level ('summary' or 'full').
    """
    aggregator = MetricsAggregator()
    aggregator.set_pr_info(owner, repo, pr)
    req_id = aggregator.start_request(llm_metrics.provider, llm_metrics.model)
    aggregator.end_request(
        req_id,
        success=True,
        # Total includes input+output; breakdown unavailable in LLMMetrics
        tokens_input=llm_metrics.total_tokens,
        tokens_output=0,  # Not tracked separately in LLMMetrics
        cost=llm_metrics.total_cost,
    )
    _display_aggregated_metrics(aggregator)

    if metrics_output:
        _export_metrics(aggregator, metrics_output, metrics_detail)


# NOTE: File path validation for CLI options is not yet needed.
# Current CLI commands use identifiers (--owner, --repo, --pr) which are validated
# by the validators above (validate_github_username and validate_github_repo).
# If file path options are added in the future (e.g., --output, --config-path),
# add InputValidator.validate_file_path() as a Click callback with an explicit
# allow_absolute policy, for example:
#   callback=lambda ctx, param, value: (
#       value
#       if InputValidator.validate_file_path(value, base_dir=str(Path.cwd()), allow_absolute=False)
#       else (_ for _ in ()).throw(click.BadParameter("invalid file path"))
#   )


@cli.command()
@click.option(
    "--pr", required=True, type=int, callback=validate_pr_number, help="Pull request number"
)
@click.option(
    "--owner",
    required=True,
    callback=validate_github_username,
    help="Repository owner",
)
@click.option(
    "--repo",
    required=True,
    callback=validate_github_repo,
    help="Repository name",
)
@click.option(
    "--config",
    type=str,
    help=(
        "Configuration preset name (conservative/balanced/aggressive/semantic/llm-enabled) "
        "or path to configuration file (YAML/TOML)"
    ),
)
@click.option(
    "--llm/--no-llm",
    default=None,
    help="Enable/disable LLM-based parsing (default: disabled for backward compatibility)",
)
@click.option(
    "--llm-provider",
    type=click.Choice(
        ["claude-cli", "openai", "anthropic", "codex-cli", "ollama"], case_sensitive=False
    ),
    help="LLM provider to use (default: claude-cli)",
)
@click.option(
    "--llm-model",
    type=str,
    help="LLM model identifier (e.g., claude-sonnet-4-5, gpt-4)",
)
@click.option(
    "--llm-preset",
    type=click.Choice(LLMPresetConfig.list_presets(), case_sensitive=False),
    help="LLM configuration preset for zero-config setup (e.g., codex-cli-free, ollama-local)",
)
@click.option(
    "--llm-api-key",
    type=str,
    help=(
        "LLM API key (for API-based providers like OpenAI/Anthropic). "
        "Can also be set via CR_LLM_API_KEY env var."
    ),
)
@click.option(
    "--llm-parallel-parsing/--no-llm-parallel-parsing",
    default=None,
    help="Enable/disable parallel comment parsing for large PRs (default: disabled)",
)
@click.option(
    "--llm-parallel-workers",
    type=int,
    help="Maximum worker threads for parallel comment parsing (default: 4)",
)
@click.option(
    "--llm-rate-limit",
    type=float,
    help="Maximum requests per second for parallel parsing (default: 10.0)",
)
@click.option(
    "--llm-confidence-threshold",
    type=float,
    help="Minimum LLM confidence (0.0-1.0) required to accept changes (default: 0.5)",
)
@click.option(
    "--llm-effort",
    type=click.Choice(["none", "low", "medium", "high"], case_sensitive=False),
    default=None,
    help="LLM effort level: none (fastest), low, medium, high (most thorough). "
    "Controls speed/cost vs accuracy tradeoff. (default: provider-specific)",
)
@click.option(
    "--cost-budget",
    type=float,
    default=None,
    callback=validate_cost_budget,
    help="Maximum LLM cost in USD (default: unlimited). Processing stops at budget limit.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Logging level (default: INFO)",
)
@click.option(
    "--log-file",
    type=click.Path(dir_okay=False),
    help="Path to log file (default: stdout only)",
)
@click.option(
    "--metrics-output",
    type=click.Path(dir_okay=False),
    help="Export LLM metrics to file (requires --show-metrics; supports .json/.csv)",
)
@click.option(
    "--metrics-detail",
    type=click.Choice(["summary", "full"], case_sensitive=False),
    default="summary",
    help="Metrics detail level: 'summary' or 'full' with per-request data",
)
@click.option(
    "--show-metrics",
    is_flag=True,
    help=(
        "Display detailed LLM metrics after analysis. Note: Latency percentiles "
        "show aggregate values; per-request tracking requires provider integration."
    ),
)
def analyze(
    pr: int,
    owner: str,
    repo: str,
    config: str | None,
    llm: bool | None,
    llm_provider: str | None,
    llm_model: str | None,
    llm_preset: str | None,
    llm_api_key: str | None,
    llm_parallel_parsing: bool | None,
    llm_parallel_workers: int | None,
    llm_rate_limit: float | None,
    llm_confidence_threshold: float | None,
    llm_effort: str | None,
    cost_budget: float | None,
    log_level: str | None,
    log_file: str | None,
    metrics_output: str | None,
    metrics_detail: str,
    show_metrics: bool,
) -> None:
    """Analyze conflicts in a pull request and print a summary to the console.

    Supports LLM-based parsing with configuration from files/env vars/CLI flags.

    Configuration precedence: CLI flags > environment variables > config file > defaults

    Args:
        pr: Pull request number.
        owner: Repository owner or organization.
        repo: Repository name.
        config: Configuration preset name or path to configuration file (YAML/TOML).
        llm: Enable (True) or disable (False) LLM-based parsing. None uses config/env/defaults.
        llm_provider: LLM provider to use (claude-cli, openai, anthropic, codex-cli, ollama).
        llm_model: LLM model identifier (e.g., claude-sonnet-4-5, gpt-4).
        llm_preset: LLM configuration preset for zero-config setup.
        llm_api_key: API key for API-based providers (OpenAI, Anthropic).
        llm_parallel_parsing: Enable (True) or disable (False) parallel comment parsing.
        llm_parallel_workers: Maximum worker threads for parallel comment parsing.
        llm_rate_limit: Maximum requests per second for parallel comment parsing.
        llm_confidence_threshold: Minimum LLM confidence (0.0-1.0) required to accept changes.
        llm_effort: LLM effort level (none/low/medium/high) for speed/cost vs accuracy tradeoff.
        cost_budget: Maximum cost in USD for LLM API calls. None for unlimited.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Path to log file for output.
        metrics_output: Path to export metrics file (.json or .csv).
        metrics_detail: Level of detail for metrics export ('summary' or 'full').
        show_metrics: Display detailed metrics with latency percentiles.

    Raises:
        click.Abort: If an error occurs while analyzing conflicts.
    """
    # Validate metrics options
    if metrics_output and not show_metrics:
        console.print(
            "[yellow]Warning: --metrics-output has no effect without --show-metrics[/yellow]"
        )

    # Load runtime configuration with proper precedence
    try:
        env_var_map = {
            "log_level": "CR_LOG_LEVEL",
            "log_file": "CR_LOG_FILE",
            "llm_enabled": "CR_LLM_ENABLED",
            "llm_provider": "CR_LLM_PROVIDER",
            "llm_model": "CR_LLM_MODEL",
            "llm_api_key": "CR_LLM_API_KEY",
            "llm_fallback_to_regex": "CR_LLM_FALLBACK_TO_REGEX",
            "llm_cache_enabled": "CR_LLM_CACHE_ENABLED",
            "llm_max_tokens": "CR_LLM_MAX_TOKENS",
            "llm_cost_budget": "CR_LLM_COST_BUDGET",
            "llm_parallel_parsing": "CR_LLM_PARALLEL_PARSING",
            "llm_parallel_max_workers": "CR_LLM_PARALLEL_WORKERS",
            "llm_rate_limit": "CR_LLM_RATE_LIMIT",
            "llm_confidence_threshold": "CR_LLM_CONFIDENCE_THRESHOLD",
            "llm_effort": "CR_LLM_EFFORT",
        }

        cli_overrides = {
            "log_level": log_level.upper() if log_level else None,
            "log_file": str(log_file) if log_file else None,
            "llm_enabled": llm,  # None, True, or False
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_api_key": llm_api_key,  # API key from CLI (highest priority)
            "llm_parallel_parsing": llm_parallel_parsing,
            "llm_parallel_max_workers": llm_parallel_workers,
            "llm_rate_limit": llm_rate_limit,
            "llm_confidence_threshold": llm_confidence_threshold,
            "llm_effort": llm_effort,
            "llm_cost_budget": cost_budget,
        }

        runtime_config, preset_name = load_runtime_config(
            config=config,
            llm_preset=llm_preset,
            llm_api_key=llm_api_key,
            cli_overrides=cli_overrides,
            env_var_map=env_var_map,
        )

        # Configure logging
        log_handler = (
            logging.FileHandler(runtime_config.log_file)
            if runtime_config.log_file
            else logging.StreamHandler()
        )
        logging.basicConfig(
            level=getattr(logging, runtime_config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[log_handler],
            force=True,
        )

    except Exception as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        raise click.Abort() from e

    # Display configuration summary
    safe_owner = sanitize_for_output(owner)
    safe_repo = sanitize_for_output(repo)
    console.print(f"Analyzing conflicts in PR #{pr} for {safe_owner}/{safe_repo}")

    if runtime_config.llm_enabled:
        console.print(
            f"[dim]LLM parsing: {runtime_config.llm_provider} ({runtime_config.llm_model})[/dim]"
        )

    # Map RuntimeConfig preset name to PresetConfig dict
    if preset_name:
        config_preset = getattr(PresetConfig, preset_name.upper(), PresetConfig.BALANCED)
    else:
        # No preset specified (using defaults or loaded from file),
        # use balanced as default resolver strategy
        config_preset = PresetConfig.BALANCED

    # Initialize LLM parser if enabled
    llm_parser, cost_tracker = _create_llm_parser(runtime_config)

    # Initialize resolver with LLM parser
    resolver = ConflictResolver(config_preset, llm_parser=llm_parser)

    with handle_llm_errors(runtime_config):
        try:
            # Analyze conflicts
            conflicts = resolver.analyze_conflicts(owner, repo, pr)

            if not conflicts:
                console.print("✅ No conflicts detected")
                return

            # Display results
            table = Table(title="Conflict Analysis")
            table.add_column("File", style="cyan")
            table.add_column("Conflicts", style="red")
            table.add_column("Type", style="yellow")
            table.add_column("Severity", style="magenta")
            table.add_column("Overlap %", style="blue")

            for conflict in conflicts:
                table.add_row(
                    conflict.file_path,
                    str(len(conflict.changes)),
                    conflict.conflict_type,
                    conflict.severity,
                    f"{conflict.overlap_percentage:.1f}%",
                )

            console.print(table)
            console.print(f"\n📊 Found {len(conflicts)} conflicts")

            # Display LLM metrics if LLM was used
            if runtime_config.llm_enabled and llm_parser:
                # Extract all changes to compute metrics
                comments = resolver._fetch_comments_with_error_context(owner, repo, pr)

                # Use parallel parsing if enabled and parser supports it
                if runtime_config.llm_parallel_parsing and isinstance(
                    llm_parser, ParallelLLMParser
                ):
                    # Create progress callback for Rich progress bar
                    progress = Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        console=console,
                    )

                    with progress:
                        task_id = progress.add_task("Parsing comments...", total=len(comments))

                        def progress_callback(completed: int, total: int) -> None:
                            """Update progress bar."""
                            progress.update(task_id, completed=completed)

                        changes = resolver.extract_changes_from_comments(
                            comments,
                            parallel_parsing=True,
                            max_workers=runtime_config.llm_parallel_max_workers,
                            progress_callback=progress_callback,
                        )
                else:
                    changes = resolver.extract_changes_from_comments(comments)

                llm_metrics = resolver._aggregate_llm_metrics(changes)

                if llm_metrics:
                    _display_llm_metrics(llm_metrics)

                # Display cost budget status if tracking enabled
                _display_cost_status(cost_tracker)

                # Show detailed aggregated metrics if --show-metrics flag is set
                if show_metrics and llm_metrics:
                    _record_and_display_metrics(
                        llm_metrics, owner, repo, pr, metrics_output, metrics_detail
                    )

        except LLMError:
            # LLM errors are handled by the context manager
            raise
        except Exception as e:
            console.print(f"❌ Error analyzing conflicts: {e}")
            logger.exception("Failed to analyze conflicts")
            raise click.Abort() from e


@cli.command()
@click.option(
    "--pr", required=True, type=int, callback=validate_pr_number, help="Pull request number"
)
@click.option(
    "--owner",
    required=True,
    callback=validate_github_username,
    help="Repository owner",
)
@click.option(
    "--repo",
    required=True,
    callback=validate_github_repo,
    help="Repository name",
)
@click.option("--strategy", default="priority", help="Resolution strategy")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate without applying changes (deprecated: use --mode=dry-run)",
)
@click.option(
    "--mode",
    type=click.Choice(
        ["all", "conflicts-only", "non-conflicts-only", "dry-run"], case_sensitive=False
    ),
    help=(
        "Application mode: 'all' (apply all changes), 'conflicts-only' (only conflicting changes), "
        "'non-conflicts-only' (only non-conflicting changes), 'dry-run' (analyze without applying)"
    ),
)
@click.option(
    "--rollback/--no-rollback", default=None, help="Enable/disable automatic rollback on failure"
)
@click.option(
    "--validation/--no-validation",
    default=None,
    help="Enable/disable pre-application validation",
)
@click.option(
    "--parallel", is_flag=True, help="Enable parallel processing of changes (experimental)"
)
@click.option(
    "--max-workers",
    type=int,
    default=None,
    help="Maximum number of worker threads for parallel processing (default: 4)",
)
@click.option(
    "--llm/--no-llm",
    default=None,
    help="Enable/disable LLM-based parsing (default: disabled for backward compatibility)",
)
@click.option(
    "--llm-provider",
    type=click.Choice(
        ["claude-cli", "openai", "anthropic", "codex-cli", "ollama"], case_sensitive=False
    ),
    help="LLM provider to use (default: claude-cli)",
)
@click.option(
    "--llm-model",
    type=str,
    help="LLM model identifier (e.g., claude-sonnet-4-5, gpt-4)",
)
@click.option(
    "--llm-preset",
    type=click.Choice(LLMPresetConfig.list_presets(), case_sensitive=False),
    help="LLM configuration preset for zero-config setup (e.g., codex-cli-free, ollama-local)",
)
@click.option(
    "--llm-api-key",
    type=str,
    help=(
        "LLM API key (for API-based providers like OpenAI/Anthropic). "
        "Can also be set via CR_LLM_API_KEY env var."
    ),
)
@click.option(
    "--llm-parallel-parsing/--no-llm-parallel-parsing",
    default=None,
    help="Enable/disable parallel comment parsing for large PRs (default: disabled)",
)
@click.option(
    "--llm-parallel-workers",
    type=int,
    help="Maximum worker threads for parallel comment parsing (default: 4)",
)
@click.option(
    "--llm-rate-limit",
    type=float,
    help="Maximum requests per second for parallel parsing (default: 10.0)",
)
@click.option(
    "--llm-confidence-threshold",
    type=float,
    help="Minimum LLM confidence (0.0-1.0) required to accept changes (default: 0.5)",
)
@click.option(
    "--llm-effort",
    type=click.Choice(["none", "low", "medium", "high"], case_sensitive=False),
    default=None,
    help="LLM effort level: none (fastest), low, medium, high (most thorough). "
    "Controls speed/cost vs accuracy tradeoff. (default: provider-specific)",
)
@click.option(
    "--cost-budget",
    type=float,
    default=None,
    callback=validate_cost_budget,
    help="Maximum LLM cost in USD (default: unlimited). Processing stops at budget limit.",
)
@click.option(
    "--config",
    type=str,
    help=(
        "Configuration preset name (conservative/balanced/aggressive/semantic/llm-enabled) "
        "or path to configuration file (YAML/TOML)"
    ),
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Logging level (default: INFO)",
)
@click.option(
    "--log-file",
    type=click.Path(dir_okay=False),
    help="Path to log file (default: stdout only)",
)
@click.option(
    "--metrics-output",
    type=click.Path(dir_okay=False),
    help="Export LLM metrics to file (requires --show-metrics; supports .json/.csv)",
)
@click.option(
    "--metrics-detail",
    type=click.Choice(["summary", "full"], case_sensitive=False),
    default="summary",
    help="Metrics detail level: 'summary' or 'full' with per-request data",
)
@click.option(
    "--show-metrics",
    is_flag=True,
    help=(
        "Display detailed LLM metrics after processing. Note: Latency percentiles "
        "show aggregate values; per-request tracking requires provider integration."
    ),
)
def apply(
    pr: int,
    owner: str,
    repo: str,
    strategy: str,
    dry_run: bool,
    mode: str | None,
    rollback: bool | None,
    validation: bool | None,
    parallel: bool,
    max_workers: int | None,
    llm: bool | None,
    llm_provider: str | None,
    llm_model: str | None,
    llm_preset: str | None,
    llm_api_key: str | None,
    llm_parallel_parsing: bool | None,
    llm_parallel_workers: int | None,
    llm_rate_limit: float | None,
    llm_confidence_threshold: float | None,
    llm_effort: str | None,
    cost_budget: float | None,
    config: str | None,
    log_level: str | None,
    log_file: str | None,
    metrics_output: str | None,
    metrics_detail: str,
    show_metrics: bool,
) -> None:
    r"""Apply or simulate applying conflict-resolution suggestions to a pull request.

    Supports multiple application modes, configuration from files/env vars/CLI flags,
    parallel processing, and automatic rollback on failure.

    Configuration precedence: CLI flags > environment variables > config file > defaults

    Args:
        pr: Pull request number.
        owner: Repository owner or organization.
        repo: Repository name.
        strategy: Resolution strategy to use (e.g., "priority").
        dry_run: (Deprecated) If True, use dry-run mode. Use --mode=dry-run instead.
        mode: Application mode (all, conflicts-only, non-conflicts-only, dry-run).
        rollback: Enable (True) or disable (False) automatic rollback on failure.
            None uses config/env/defaults.
        validation: Enable (True) or disable (False) pre-application validation.
            None uses config/env/defaults.
        parallel: Enable parallel processing of changes.
        max_workers: Maximum number of worker threads (default: 4).
        llm: Enable (True) or disable (False) LLM-based parsing. None uses config/env/defaults.
        llm_provider: LLM provider to use (claude-cli, openai, anthropic, codex-cli, ollama).
        llm_model: LLM model identifier (e.g., claude-sonnet-4-5, gpt-4).
        llm_preset: LLM configuration preset for zero-config setup
            (codex-cli-free, ollama-local, claude-cli-sonnet, openai-api-mini,
            anthropic-api-balanced).
        llm_api_key: API key for API-based providers (OpenAI, Anthropic).
        llm_parallel_parsing: Enable parallel LLM comment parsing for large PRs.
        llm_parallel_workers: Maximum worker threads for parallel LLM parsing (1-32).
        llm_rate_limit: Rate limit for LLM API calls (requests/second, minimum 0.1).
        llm_confidence_threshold: Minimum LLM confidence (0.0-1.0) required to accept changes.
        llm_effort: LLM effort level (none/low/medium/high) for speed/cost vs accuracy tradeoff.
        cost_budget: Maximum cost in USD for LLM API calls. None for unlimited.
        config: Configuration preset name or path to configuration file (YAML or TOML).
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Path to log file for output.
        metrics_output: Path to export LLM metrics file (.json or .csv), or None to skip export.
        metrics_detail: Metrics export detail level ("summary" or "full" with per-request data).
        show_metrics: If True, display detailed LLM metrics to stdout after processing.

    Raises:
        click.Abort: If an error occurs while analyzing or applying suggestions.

    Examples:
        # Apply all changes with default settings
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo

        # Dry-run mode to analyze without applying
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo --mode dry-run

        # Use LLM preset for zero-config setup (free, no API key)
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo \\
            --llm-preset codex-cli-free

        # Use LLM preset with API key for paid providers
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo \\
            --llm-preset openai-api-mini --llm-api-key sk-...

        # Apply only conflicting changes with parallel processing
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo \\
            --mode conflicts-only --parallel --max-workers 8

        # Load configuration from file
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo \\
            --config /path/to/config.yaml
    """
    # Validate metrics options
    if metrics_output and not show_metrics:
        console.print(
            "[yellow]Warning: --metrics-output has no effect without --show-metrics[/yellow]"
        )

    # Load runtime configuration with proper precedence
    try:
        # Handle deprecated --dry-run flag (maps to mode)
        if dry_run and mode:
            console.print(
                "[yellow]Warning: Both --dry-run and --mode specified. Using --mode.[/yellow]"
            )
        elif dry_run:
            mode = "dry-run"
            console.print(
                "[yellow]Warning: --dry-run is deprecated. Use --mode=dry-run instead.[/yellow]"
            )

        env_var_map = {
            "mode": "CR_MODE",
            "enable_rollback": "CR_ENABLE_ROLLBACK",
            "validate_before_apply": "CR_VALIDATE",
            "parallel_processing": "CR_PARALLEL",
            "max_workers": "CR_MAX_WORKERS",
            "log_level": "CR_LOG_LEVEL",
            "log_file": "CR_LOG_FILE",
            "llm_enabled": "CR_LLM_ENABLED",
            "llm_provider": "CR_LLM_PROVIDER",
            "llm_model": "CR_LLM_MODEL",
            "llm_api_key": "CR_LLM_API_KEY",
            "llm_fallback_to_regex": "CR_LLM_FALLBACK_TO_REGEX",
            "llm_cache_enabled": "CR_LLM_CACHE_ENABLED",
            "llm_max_tokens": "CR_LLM_MAX_TOKENS",
            "llm_cost_budget": "CR_LLM_COST_BUDGET",
            "llm_parallel_parsing": "CR_LLM_PARALLEL_PARSING",
            "llm_parallel_max_workers": "CR_LLM_PARALLEL_WORKERS",
            "llm_rate_limit": "CR_LLM_RATE_LIMIT",
            "llm_confidence_threshold": "CR_LLM_CONFIDENCE_THRESHOLD",
            "llm_effort": "CR_LLM_EFFORT",
        }

        cli_overrides = {
            "mode": mode,
            "enable_rollback": rollback,  # None, True, or False
            "validate_before_apply": validation,  # None, True, or False
            "parallel_processing": True if parallel else None,
            "max_workers": max_workers,
            "log_level": log_level.upper() if log_level else None,
            "log_file": str(log_file) if log_file else None,
            "llm_enabled": llm,  # None, True, or False
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_api_key": llm_api_key,  # API key from CLI (highest priority)
            "llm_parallel_parsing": llm_parallel_parsing,
            "llm_parallel_max_workers": llm_parallel_workers,
            "llm_rate_limit": llm_rate_limit,
            "llm_confidence_threshold": llm_confidence_threshold,
            "llm_effort": llm_effort,
            "llm_cost_budget": cost_budget,
        }

        runtime_config, preset_name = load_runtime_config(
            config=config,
            llm_preset=llm_preset,
            llm_api_key=llm_api_key,
            cli_overrides=cli_overrides,
            env_var_map=env_var_map,
        )

        # Configure logging
        log_handler = (
            logging.FileHandler(runtime_config.log_file)
            if runtime_config.log_file
            else logging.StreamHandler()
        )
        logging.basicConfig(
            level=getattr(logging, runtime_config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[log_handler],
            force=True,
        )

    except Exception as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        raise click.Abort() from e

    # Display configuration summary
    safe_owner = sanitize_for_output(owner)
    safe_repo = sanitize_for_output(repo)
    safe_strategy = sanitize_for_output(strategy)

    console.print("\n[bold]PR Conflict Resolver[/bold]")
    console.print(f"Repository: {safe_owner}/{safe_repo} PR #{pr}")
    console.print(f"Strategy: {safe_strategy}")
    console.print(f"Mode: [cyan]{runtime_config.mode}[/cyan]")
    rollback_status = (
        "[green]enabled[/green]" if runtime_config.enable_rollback else "[yellow]disabled[/yellow]"
    )
    console.print(f"Rollback: {rollback_status}")
    validation_status = (
        "[green]enabled[/green]"
        if runtime_config.validate_before_apply
        else "[yellow]disabled[/yellow]"
    )
    console.print(f"Validation: {validation_status}")
    if runtime_config.parallel_processing:
        console.print(
            f"Parallel processing: [cyan]enabled[/cyan] (workers: {runtime_config.max_workers})"
        )
    console.print()

    # Get configuration preset (map from RuntimeConfig preset to PresetConfig)
    if preset_name:
        # Map preset name to PresetConfig attribute
        config_preset = getattr(PresetConfig, preset_name.upper(), PresetConfig.BALANCED)
    else:
        # No preset specified (using defaults or loaded from file),
        # use balanced as default resolver strategy
        config_preset = PresetConfig.BALANCED

    # Initialize LLM parser if enabled
    llm_parser, cost_tracker = _create_llm_parser(runtime_config)

    # Initialize resolver with LLM parser
    resolver = ConflictResolver(config_preset, llm_parser=llm_parser)

    with handle_llm_errors(runtime_config):
        try:
            if runtime_config.mode == ApplicationMode.DRY_RUN:
                # Dry-run mode: Just analyze conflicts
                console.print(
                    "[yellow]DRY RUN MODE:[/yellow] Analyzing conflicts without applying changes"
                )
                conflicts = resolver.analyze_conflicts(owner, repo, pr)
                console.print(f"📊 Would process {len(conflicts)} conflicts")
            else:
                # Apply mode: Resolve conflicts with configured settings
                console.print("Resolving conflicts...")
                # Convert ApplicationMode enum to string for resolver
                mode_str = runtime_config.mode.value  # Use the enum's value directly
                result = resolver.resolve_pr_conflicts(
                    owner,
                    repo,
                    pr,
                    mode=mode_str,
                    validate=runtime_config.validate_before_apply,
                    parallel=runtime_config.parallel_processing,
                    max_workers=runtime_config.max_workers,
                    enable_rollback=runtime_config.enable_rollback,
                )

                # Display results
                console.print("\n[bold green]✅ Results:[/bold green]")
                console.print(f"  Applied: {result.applied_count} suggestions")
                console.print(f"  Skipped: {result.conflict_count} conflicts")
                console.print(f"  Success rate: {result.success_rate:.1f}%")

                if result.conflict_count > 0:
                    console.print("\n[yellow]💡 Some conflicts require manual review[/yellow]")

                # Display LLM metrics if available
                if result.llm_metrics:
                    _display_llm_metrics(result.llm_metrics)

                    # Display cost budget status if tracking enabled
                    _display_cost_status(cost_tracker)

                    # Show detailed aggregated metrics if --show-metrics flag is set
                    if show_metrics:
                        _record_and_display_metrics(
                            result.llm_metrics,
                            owner,
                            repo,
                            pr,
                            metrics_output,
                            metrics_detail,
                        )

        except LLMError:
            # LLM errors are handled by the context manager
            raise
        except Exception as e:
            console.print(f"\n[red]❌ Error applying suggestions: {e}[/red]")
            logger.exception("Failed to apply conflict resolution")
            raise click.Abort() from e


@cli.command()
@click.option(
    "--pr", required=True, type=int, callback=validate_pr_number, help="Pull request number"
)
@click.option(
    "--owner",
    required=True,
    callback=validate_github_username,
    help="Repository owner",
)
@click.option(
    "--repo",
    required=True,
    callback=validate_github_repo,
    help="Repository name",
)
@click.option("--config", default="balanced", help="Configuration preset")
def simulate(pr: int, owner: str, repo: str, config: str) -> None:
    """Simulate resolving pull request conflicts and print a summary of what would be applied.

    Analyzes conflicts for the specified PR using the named configuration preset and
    prints a simulation report showing total conflicting changes, how many would be
    applied or skipped, and the resulting success rate.

    Args:
        pr (int): Pull request number.
        owner (str): Repository owner or organization.
        repo (str): Repository name.
        config (str): Preset configuration name (mapped via PresetConfig.<NAME>,
            defaults to BALANCED).

    Raises:
        click.Abort: If an unexpected error occurs during analysis.
    """
    safe_owner = sanitize_for_output(owner)
    safe_repo = sanitize_for_output(repo)
    safe_config = sanitize_for_output(config)

    console.print(f"Simulating conflict resolution for PR #{pr} for {safe_owner}/{safe_repo}")
    console.print(f"Using configuration: {safe_config}")

    # Get configuration preset
    config_preset = getattr(PresetConfig, config.upper(), PresetConfig.BALANCED)

    # Initialize resolver
    resolver = ConflictResolver(config_preset)

    try:
        # Analyze conflicts
        conflicts = resolver.analyze_conflicts(owner, repo, pr)

        if not conflicts:
            console.print("✅ No conflicts detected")
            return

        # Simulate resolution using actual strategy
        resolutions = resolver.resolve_conflicts(conflicts)

        total_changes = sum(len(conflict.changes) for conflict in conflicts)
        would_apply = sum(len(resolution.applied_changes) for resolution in resolutions)
        would_skip = sum(len(resolution.skipped_changes) for resolution in resolutions)
        success_rate = (would_apply / total_changes) * 100 if total_changes else 0

        console.print("📊 Simulation Results:")
        console.print(f"  • Total changes: {total_changes}")
        console.print(f"  • Would apply: {would_apply}")
        console.print(f"  • Would skip: {would_skip}")
        console.print(f"  • Success rate: {success_rate:.1f}%")

    except Exception as e:
        console.print(f"❌ Error simulating resolution: {e}")
        raise click.Abort() from e


if __name__ == "__main__":
    cli()
