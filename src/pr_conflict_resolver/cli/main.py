"""Command-line interface for pr-conflict-resolver."""

import re

import click
from rich.console import Console
from rich.table import Table

from ..config.presets import PresetConfig
from ..core.resolver import ConflictResolver
from ..security.input_validator import InputValidator

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Create the main Click command-line interface for the CodeRabbit conflict resolver.

    Defines the top-level `cli` command group with a version option and registers the
    `analyze`, `apply`, and `simulate` subcommands; configures the Rich console used
    for styled terminal output.
    """


MAX_CLI_NAME_LENGTH = 512


# Compiled pattern for detecting potential shell/env injection constructs.
_INJECTION_PATTERN = re.compile(
    r"(?:\$\{|\$\(|`|\$[A-Za-z_][A-Za-z0-9_]*)|[\n\r\x00|;&<>*\?\[\]\{\}\(\)\\\'\"]"
)


def sanitize_for_output(value: str) -> str:
    """Redact potentially dangerous injection patterns before printing.

    Detects common shell and environment-variable injection constructs and returns
    a redacted placeholder if any are present. Otherwise returns the original value.

    Args:
        value (str): The string to sanitize for terminal output.

    Returns:
        str: "[REDACTED]" if dangerous patterns are found; otherwise the original string.
    """
    # Patterns: $VAR, ${VAR}, $(...), backticks, or any dangerous characters
    # including control chars (\n, \r, \x00), shell metacharacters, and quotes
    if _INJECTION_PATTERN.search(value):
        return "[REDACTED]"
    return value


def validate_github_identifier(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """Validate GitHub owner/repo identifiers for safety.

    Enforces strict length and character constraints and rejects common
    shell/environment injection patterns.

    Args:
        ctx: Click context object.
        param: Click parameter object.
        value: Identifier value to validate.

    Returns:
        str: The validated identifier value.

    Raises:
        click.BadParameter: If identifier validation fails.
    """
    # Basic type/emptiness checks
    if not isinstance(value, str) or not value.strip():
        raise click.BadParameter("identifier required")

    # Enforce maximum length
    if len(value) > MAX_CLI_NAME_LENGTH:
        raise click.BadParameter(f"identifier too long (max {MAX_CLI_NAME_LENGTH})")

    # Disallow slashes and whitespace; GitHub identifiers are single segments
    if "/" in value or "\\" in value or any(ch.isspace() for ch in value):
        raise click.BadParameter("identifier must be a single segment (no slashes or spaces)")

    # Allowed characters: letters, digits, dot, underscore, hyphen
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        raise click.BadParameter(
            "identifier contains invalid characters; "
            "allowed: letters, digits, dot, underscore, hyphen"
        )
    return value


def validate_path_option(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """Validate CLI path option for security using Click callback.

    Args:
        ctx: Click context object
        param: Click parameter object
        value: Path value to validate

    Returns:
        str: The validated path value

    Raises:
        click.BadParameter: If path validation fails
    """
    # Enforce maximum length for CLI identifiers
    if len(value) > MAX_CLI_NAME_LENGTH:
        raise click.BadParameter(
            f"{param.human_readable_name or param.name}: value too long (max {MAX_CLI_NAME_LENGTH})"
        )

    if not InputValidator.validate_file_path(value, allow_absolute=False):
        raise click.BadParameter(f"{param.human_readable_name or param.name}: invalid path")
    return value


@cli.command()
@click.option("--pr", required=True, type=int, help="Pull request number")
@click.option(
    "--owner",
    required=True,
    callback=validate_github_identifier,
    help="Repository owner",
)
@click.option(
    "--repo",
    required=True,
    callback=validate_github_identifier,
    help="Repository name",
)
@click.option("--config", default="balanced", help="Configuration preset")
def analyze(pr: int, owner: str, repo: str, config: str) -> None:
    """Analyze conflicts in a pull request and print a summary to the console.

    Parameters:
        pr (int): Pull request number.
        owner (str): Repository owner or organization.
        repo (str): Repository name.
        config (str): Configuration preset name (e.g., "balanced"); falls back to
            the default preset if not recognized.

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
@click.option("--pr", required=True, type=int, help="Pull request number")
@click.option(
    "--owner",
    required=True,
    callback=validate_github_identifier,
    help="Repository owner",
)
@click.option(
    "--repo",
    required=True,
    callback=validate_github_identifier,
    help="Repository name",
)
@click.option("--strategy", default="priority", help="Resolution strategy")
@click.option("--dry-run", is_flag=True, help="Simulate without applying changes")
def apply(pr: int, owner: str, repo: str, strategy: str, dry_run: bool) -> None:
    """Apply or simulate applying conflict-resolution suggestions to a pull request.

    When `dry_run` is True, analyzes conflicts and reports how many would be
    processed without making changes. Otherwise, applies suggestions for the given
    PR using the specified strategy and reports counts and success rate.

    Parameters:
        pr (int): Pull request number.
        owner (str): Repository owner or organization.
        repo (str): Repository name.
        strategy (str): Resolution strategy to use (e.g., "priority").
        dry_run (bool): If True, do not apply changes; only simulate and report.

    Raises:
        click.Abort: If an error occurs while analyzing or applying suggestions.
    """
    if dry_run:
        console.print(f"[yellow]DRY RUN:[/yellow] Would apply suggestions to PR #{pr}")
    else:
        console.print(f"Applying suggestions to PR #{pr}")

    safe_strategy = sanitize_for_output(strategy)
    console.print(f"Using strategy: {safe_strategy}")

    # Get configuration preset
    config_preset = PresetConfig.BALANCED

    # Initialize resolver
    resolver = ConflictResolver(config_preset)

    try:
        if dry_run:
            # Just analyze conflicts
            conflicts = resolver.analyze_conflicts(owner, repo, pr)
            console.print(f"📊 Would process {len(conflicts)} conflicts")
        else:
            # Resolve conflicts
            result = resolver.resolve_pr_conflicts(owner, repo, pr)

            # Display results
            console.print(f"✅ Applied {result.applied_count} suggestions")
            console.print(f"⚠️  Skipped {result.conflict_count} conflicts")
            console.print(f"📈 Success rate: {result.success_rate:.1f}%")

            if result.conflict_count > 0:
                console.print("💡 Some conflicts require manual review")

    except Exception as e:
        console.print(f"❌ Error applying suggestions: {e}")
        raise click.Abort() from e


@cli.command()
@click.option("--pr", required=True, type=int, help="Pull request number")
@click.option(
    "--owner",
    required=True,
    callback=validate_github_identifier,
    help="Repository owner",
)
@click.option(
    "--repo",
    required=True,
    callback=validate_github_identifier,
    help="Repository name",
)
@click.option("--config", default="balanced", help="Configuration preset")
def simulate(pr: int, owner: str, repo: str, config: str) -> None:
    """Simulate resolving pull request conflicts and print a summary of what would be applied.

    Analyzes conflicts for the specified PR using the named configuration preset and
    prints a simulation report showing total conflicting changes, how many would be
    applied or skipped, and the resulting success rate.

    Parameters:
        config (str): Name of the preset configuration to use (mapped to PresetConfig
            by uppercasing); defaults to BALANCED if not found.

    Raises:
        click.Abort: If an unexpected error occurs during analysis.
    """
    console.print(f"Simulating conflict resolution for PR #{pr}")
    safe_config = sanitize_for_output(config)
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

        # Simulate resolution
        total_changes = sum(len(conflict.changes) for conflict in conflicts)
        would_apply = sum(1 for conflict in conflicts if conflict.severity != "high")
        would_skip = len(conflicts) - would_apply
        success_rate = (would_apply / len(conflicts)) * 100 if conflicts else 0

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
