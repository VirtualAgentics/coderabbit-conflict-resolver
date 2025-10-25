"""Command-line interface for pr-conflict-resolver."""

import click
from rich.console import Console
from rich.table import Table

from ..config.presets import PresetConfig
from ..core.resolver import ConflictResolver

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Create the main Click command-line interface for the CodeRabbit conflict resolver.

    Defines the top-level `cli` command group with a version option and registers the
    `analyze`, `apply`, and `simulate` subcommands; configures the Rich console used
    for styled terminal output.
    """


@cli.command()
@click.option("--pr", required=True, help="Pull request number")
@click.option("--owner", required=True, help="Repository owner")
@click.option("--repo", required=True, help="Repository name")
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
    console.print(f"Analyzing conflicts in PR #{pr} for {owner}/{repo}")
    console.print(f"Using configuration: {config}")

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
@click.option("--pr", required=True, help="Pull request number")
@click.option("--owner", required=True, help="Repository owner")
@click.option("--repo", required=True, help="Repository name")
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

    console.print(f"Using strategy: {strategy}")

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
@click.option("--pr", required=True, help="Pull request number")
@click.option("--owner", required=True, help="Repository owner")
@click.option("--repo", required=True, help="Repository name")
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
    console.print(f"Using configuration: {config}")

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
