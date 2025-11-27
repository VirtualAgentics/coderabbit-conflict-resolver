Review Bot Automator Documentation
===================================

An intelligent, automated conflict resolution system for GitHub PR comments, specifically designed for `CodeRabbit AI <https://coderabbit.ai>`_ but extensible to other code review bots.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting-started
   architecture
   configuration
   llm-configuration
   llm-provider-guide
   migration
   conflict-types
   resolution-strategies
   api-reference
   troubleshooting
   contributing

Quick Start
-----------

Install the package:

.. code-block:: bash

   pip install review-bot-automator

Basic usage:

.. code-block:: python

   from review_bot_automator import ConflictResolver
   from review_bot_automator.config import PresetConfig

   resolver = ConflictResolver(config=PresetConfig.BALANCED)
   results = resolver.resolve_pr_conflicts(
       owner="VirtualAgentics",
       repo="my-repo",
       pr_number=123
   )

   print(f"Applied: {results.applied_count}")
   print(f"Conflicts: {results.conflict_count}")
   print(f"Success rate: {results.success_rate}%")

Command-line interface:

.. code-block:: bash

   # Analyze conflicts in a PR
   pr-resolve analyze --pr 123 --owner VirtualAgentics --repo my-repo

   # Apply suggestions with conflict resolution
   pr-resolve apply --pr 123 --owner VirtualAgentics --repo my-repo --strategy priority

   # Simulate without applying changes
   pr-resolve simulate --pr 123 --owner VirtualAgentics --repo my-repo --config balanced

Features
--------

* **Intelligent Conflict Analysis**: Semantic understanding of JSON, YAML, TOML structure
* **Smart Resolution Strategies**: Priority-based resolution with user selections taking precedence
* **File-Type Handlers**: Specialized handlers for different file types
* **Learning & Optimization**: ML-assisted priority learning and conflict pattern recognition
* **Configuration Presets**: Conservative, Balanced, Aggressive, and Semantic modes

Architecture
------------

The system follows a modular architecture with clear separation of concerns:

* **Conflict Detection**: Analyzes changes for potential conflicts
* **File Handlers**: Specialized handlers for different file types
* **Resolution Strategies**: Different approaches to conflict resolution
* **GitHub Integration**: Fetches and parses PR comments
* **Configuration**: Flexible configuration system with presets

For detailed architecture information, see :doc:`architecture`.

API Reference
-------------

.. toctree::
   :maxdepth: 2

   api/core
   api/analysis
   api/handlers
   api/strategies
   api/integrations
   api/config

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
