"""Command-line interface for pr-conflict-resolver."""

import hashlib
import logging
import re

import click
from rich.console import Console
from rich.table import Table

from pr_conflict_resolver.config.presets import PresetConfig
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
# by validate_github_identifier(). If file path options are added in the future
# (e.g., --output, --config-path), add InputValidator.validate_file_path() as a
# Click callback with appropriate allow_absolute setting.


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
