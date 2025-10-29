#!/usr/bin/env python3
"""Add timing metrics and failure notifications to workflows that already have summaries."""

import re
from pathlib import Path

# Workflows that need timing + notifications added (already have summaries)
WORKFLOWS = [
    ".github/workflows/ci.yml",
    ".github/workflows/security.yml",
    ".github/workflows/docs.yml",
    ".github/workflows/docs-deploy.yml",
]

TIMING_STEP = """      - name: Record job start time
        id: job-start
        run: echo "start_time=$(date +%s)" >> $GITHUB_OUTPUT

"""

FAILURE_NOTIFICATION = """
      - name: Notify on failure
        if: failure()
        run: |
          echo "::error::Workflow failed - check logs for details"
          echo "## ❌ Workflow Failed" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "This workflow has failed." >> $GITHUB_STEP_SUMMARY
          echo "Please check the logs above for error details." >> $GITHUB_STEP_SUMMARY
"""

TIMING_CALCULATION = """
          # Calculate job duration
          END_TIME=$(date +%s)
          START_TIME=${{ steps.job-start.outputs.start_time }}
          DURATION=$((END_TIME - START_TIME))
          DURATION_MIN=$((DURATION / 60))
          DURATION_SEC=$((DURATION % 60))

"""

DURATION_OUTPUT = (
    """          echo "**Job Duration:** ${DURATION_MIN}m ${DURATION_SEC}s" """
    """>> $GITHUB_STEP_SUMMARY\n"""
)


def add_timing_to_workflow(file_path: Path) -> None:
    """Add timing metrics and failure notification to a workflow file."""
    content = file_path.read_text()

    # Skip if already has timing
    if "Record job start time" in content:
        print(f"✅ {file_path.name} already has timing - skipping")
        return

    # Add timing step after "steps:"
    content = re.sub(r"(\n\s+steps:\n)", r"\1" + TIMING_STEP, content, count=1)

    # Add timing calculation to existing summary steps
    # Find summary generation steps and add timing calc
    if "generate" in content.lower() and "summary" in content.lower():
        # Add timing calculation at the start of summary generation
        content = re.sub(
            r"(name:.*[Gg]enerate.*[Ss]ummary\n\s+if: always\(\)\n\s+run: \|)",
            r"\1" + TIMING_CALCULATION,
            content,
        )

        # Add duration output after "Workflow Status" or similar
        content = re.sub(
            r'(echo "##.*Summary" >> \$GITHUB_STEP_SUMMARY\n\s+echo "" >> \$GITHUB_STEP_SUMMARY\n)',
            r"\1" + DURATION_OUTPUT,
            content,
        )

    # Add failure notification at the end of steps (before closing the workflow)
    content = content.rstrip() + FAILURE_NOTIFICATION + "\n"

    # Write back
    file_path.write_text(content)
    print(f"✅ Updated {file_path.name}")


def main() -> None:
    """Main function."""
    print("Adding observability features to workflows...")

    for workflow_path in WORKFLOWS:
        file_path = Path(workflow_path)
        if file_path.exists():
            try:
                add_timing_to_workflow(file_path)
            except Exception as e:
                print(f"❌ Error updating {file_path.name}: {e}")
        else:
            print(f"⚠️  {workflow_path} not found")

    print("\n✅ Workflow observability updates complete!")


if __name__ == "__main__":
    main()
