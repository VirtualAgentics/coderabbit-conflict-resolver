"""Command-line interface for pr-conflict-resolver."""

import hashlib
import logging
import os
import re
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from pr_conflict_resolver.config.presets import PresetConfig
from pr_conflict_resolver.config.runtime_config import (
    PRESET_NAMES,
    ApplicationMode,
    RuntimeConfig,
)
from pr_conflict_resolver.core.resolver import ConflictResolver

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Create the main Click command-line interface for the CodeRabbit conflict resolver.

    Defines the top-level `cli` command group with a version option and registers the
    `analyze`, `apply`, and `simulate` subcommands; configures the Rich console used
    for styled terminal output.
    """


MAX_GITHUB_USERNAME_LENGTH = 39
MAX_GITHUB_REPO_LENGTH = 100


# Compiled pattern for detecting control characters only.
_INJECTION_PATTERN = re.compile(r"[\x00-\x1f\x7f]")  # Control chars only


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
@click.option("--config", default="balanced", help="Configuration preset")
def analyze(pr: int, owner: str, repo: str, config: str) -> None:
    """Analyze conflicts in a pull request and print a summary to the console.

    Args:
        pr (int): Pull request number.
        owner (str): Repository owner or organization.
        repo (str): Repository name.
        config (str): Configuration preset (e.g., "balanced"); falls back to default if unknown.

    Raises:
        click.Abort: If an error occurs while analyzing conflicts.
    """
    safe_config = sanitize_for_output(config)

    safe_owner = sanitize_for_output(owner)
    safe_repo = sanitize_for_output(repo)
    console.print(f"Analyzing conflicts in PR #{pr} for {safe_owner}/{safe_repo}")
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

    except Exception as e:
        console.print(f"❌ Error analyzing conflicts: {e}")
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
@click.option("--no-rollback", is_flag=True, help="Disable automatic rollback on failure")
@click.option("--no-validation", is_flag=True, help="Disable pre-application validation")
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
    "--config",
    type=str,
    help=(
        "Configuration preset name (conservative/balanced/aggressive/semantic) "
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
def apply(
    pr: int,
    owner: str,
    repo: str,
    strategy: str,
    dry_run: bool,
    mode: str | None,
    no_rollback: bool,
    no_validation: bool,
    parallel: bool,
    max_workers: int | None,
    config: str | None,
    log_level: str | None,
    log_file: str | None,
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
        no_rollback: Disable automatic rollback on failure.
        no_validation: Disable pre-application validation.
        parallel: Enable parallel processing of changes.
        max_workers: Maximum number of worker threads (default: 4).
        config: Path to configuration file (YAML or TOML).
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Path to log file for output.

    Raises:
        click.Abort: If an error occurs while analyzing or applying suggestions.

    Examples:
        # Apply all changes with default settings
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo

        # Dry-run mode to analyze without applying
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo --mode dry-run

        # Apply only conflicting changes with parallel processing
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo \\
            --mode conflicts-only --parallel --max-workers 8

        # Load configuration from file
        $ pr-resolve apply --pr 123 --owner myorg --repo myrepo \\
            --config /path/to/config.yaml
    """
    # Load runtime configuration with proper precedence
    try:
        # Step 1: Load base configuration (preset, file, or defaults)
        preset_name = None  # Track which preset was loaded (if any)
        if config:
            # Check if config is a preset name or file path
            if config.lower() in PRESET_NAMES:
                # Load preset configuration
                preset_name = config.lower()
                preset_method = getattr(RuntimeConfig, f"from_{preset_name}")
                runtime_config = preset_method()
                console.print(f"[dim]Loaded preset configuration: {config}[/dim]")
            else:
                # Load from configuration file
                config_path = Path(config)
                runtime_config = RuntimeConfig.from_file(config_path)
                console.print(f"[dim]Loaded configuration from: {config}[/dim]")
        else:
            # Start with defaults when no config file/preset specified
            runtime_config = RuntimeConfig.from_defaults()
            preset_name = "balanced"  # Default preset

        # Step 2: Apply environment variable overrides
        # Extract only the env vars that are actually set (not defaults)
        env_overrides: dict[str, str | bool | int] = {}
        if "CR_MODE" in os.environ:
            env_overrides["mode"] = os.environ["CR_MODE"]
        if "CR_ENABLE_ROLLBACK" in os.environ:
            env_overrides["enable_rollback"] = os.environ["CR_ENABLE_ROLLBACK"].lower() in (
                "true",
                "1",
                "yes",
                "on",
            )
        if "CR_VALIDATE" in os.environ:
            env_overrides["validate_before_apply"] = os.environ["CR_VALIDATE"].lower() in (
                "true",
                "1",
                "yes",
                "on",
            )
        if "CR_PARALLEL" in os.environ:
            env_overrides["parallel_processing"] = os.environ["CR_PARALLEL"].lower() in (
                "true",
                "1",
                "yes",
                "on",
            )
        if "CR_MAX_WORKERS" in os.environ:
            env_overrides["max_workers"] = int(os.environ["CR_MAX_WORKERS"])
        if "CR_LOG_LEVEL" in os.environ:
            env_overrides["log_level"] = os.environ["CR_LOG_LEVEL"].upper()
        if "CR_LOG_FILE" in os.environ:
            env_overrides["log_file"] = os.environ["CR_LOG_FILE"]

        if env_overrides:
            runtime_config = runtime_config.merge_with_cli(**env_overrides)
            console.print(
                f"[dim]Applied {len(env_overrides)} environment variable override(s)[/dim]"
            )

        # Step 3: Apply CLI overrides
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

        cli_overrides = {
            "mode": mode,
            "enable_rollback": False if no_rollback else None,
            "validate_before_apply": False if no_validation else None,
            "parallel_processing": True if parallel else None,
            "max_workers": max_workers,
            "log_level": log_level.upper() if log_level else None,
            "log_file": str(log_file) if log_file else None,
        }
        runtime_config = runtime_config.merge_with_cli(**cli_overrides)

        # Step 4: Configure logging
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
        # No preset specified (loaded from file), use balanced as default
        config_preset = PresetConfig.BALANCED

    # Initialize resolver
    resolver = ConflictResolver(config_preset)

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
