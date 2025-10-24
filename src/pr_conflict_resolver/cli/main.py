"""Command-line interface for pr-conflict-resolver."""

import click
from rich.console import Console
from rich.table import Table

from ..core.resolver import ConflictResolver
from ..config.presets import PresetConfig

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """CodeRabbit Conflict Resolver - Intelligent conflict resolution for GitHub PR comments."""
    pass


@cli.command()
@click.option("--pr", required=True, help="Pull request number")
@click.option("--owner", required=True, help="Repository owner")
@click.option("--repo", required=True, help="Repository name")
@click.option("--config", default="balanced", help="Configuration preset")
def analyze(pr: int, owner: str, repo: str, config: str):
    """Analyze conflicts in a pull request."""
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
                f"{conflict.overlap_percentage:.1f}%"
            )
        
        console.print(table)
        console.print(f"\n📊 Found {len(conflicts)} conflicts")
        
    except Exception as e:
        console.print(f"❌ Error analyzing conflicts: {e}")
        raise click.Abort()


@cli.command()
@click.option("--pr", required=True, help="Pull request number")
@click.option("--owner", required=True, help="Repository owner")
@click.option("--repo", required=True, help="Repository name")
@click.option("--strategy", default="priority", help="Resolution strategy")
@click.option("--dry-run", is_flag=True, help="Simulate without applying changes")
def apply(pr: int, owner: str, repo: str, strategy: str, dry_run: bool):
    """Apply suggestions with conflict resolution."""
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
        raise click.Abort()


@cli.command()
@click.option("--pr", required=True, help="Pull request number")
@click.option("--owner", required=True, help="Repository owner")
@click.option("--repo", required=True, help="Repository name")
@click.option("--config", default="balanced", help="Configuration preset")
def simulate(pr: int, owner: str, repo: str, config: str):
    """Simulate conflict resolution without applying changes."""
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
        raise click.Abort()


if __name__ == "__main__":
    cli()
