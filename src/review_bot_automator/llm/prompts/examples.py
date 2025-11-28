# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Few-shot examples for LLM prompt engineering.

This module provides curated examples demonstrating how to parse different
CodeRabbit comment formats. These examples serve as training data for the
LLM to understand the expected input → output transformation.

Each example shows:
- Input: A specific comment format
- Output: The corresponding ParsedChange JSON
- Confidence rationale

These examples are used in few-shot prompting to improve parsing accuracy.
"""

from typing import Any

# Example 1: Diff block (highest confidence format)
EXAMPLE_DIFF_BLOCKS = {
    "comment": """
Apply this security fix to prevent SQL injection:

```diff
@@ -45,3 +45,5 @@ def get_user(user_id):
 def get_user(user_id):
     conn = database.connect()
-    query = f"SELECT * FROM users WHERE id = {user_id}"
+    # Use parameterized query to prevent SQL injection
+    query = "SELECT * FROM users WHERE id = ?"
+    result = conn.execute(query, (user_id,))
```

This change uses parameterized queries instead of string formatting.
""",
    "output": [
        {
            "file_path": "src/database.py",
            "start_line": 45,
            "end_line": 49,
            "new_content": (
                "def get_user(user_id):\n    conn = database.connect()\n    "
                "# Use parameterized query to prevent SQL injection\n    "
                'query = "SELECT * FROM users WHERE id = ?"\n    '
                "result = conn.execute(query, (user_id,))"
            ),
            "change_type": "modification",
            "confidence": 0.98,
            "rationale": "Security fix: prevent SQL injection by using parameterized queries",
            "risk_level": "high",
        }
    ],
}

# Example 2: Suggestion block (common format, high confidence)
EXAMPLE_SUGGESTIONS = {
    "comment": """
Refactor this function to improve readability:

```suggestion
def calculate_total(items):
    \"\"\"Calculate total price with tax.\"\"\"
    subtotal = sum(item.price for item in items)
    tax = subtotal * 0.08
    return subtotal + tax
```

This adds a docstring and breaks the calculation into clear steps.
""",
    "output": [
        {
            "file_path": "src/checkout.py",
            "start_line": 23,
            "end_line": 27,
            "new_content": (
                'def calculate_total(items):\n    """Calculate total price with tax."""\n'
                "    subtotal = sum(item.price for item in items)\n"
                "    tax = subtotal * 0.08\n    return subtotal + tax"
            ),
            "change_type": "modification",
            "confidence": 0.92,
            "rationale": "Improve readability with docstring and clear calculation steps",
            "risk_level": "low",
        }
    ],
}

# Example 3: Natural language with specific line reference (medium confidence)
EXAMPLE_NATURAL_LANGUAGE = {
    "comment": """
**Performance Issue**

On line 67, the database query is executed inside the loop. This causes N+1 queries
which will be slow for large datasets.

Move the query outside the loop and fetch all records at once using `WHERE id IN (...)`.
This will reduce N queries to 1 query.

**Risk**: High - affects production performance
""",
    "output": [
        {
            "file_path": "src/user_service.py",
            "start_line": 67,
            "end_line": 67,
            "new_content": (
                "# TODO: Move database query outside loop to prevent N+1 queries\n"
                "# Use WHERE id IN (...) to fetch all records at once"
            ),
            "change_type": "modification",
            "confidence": 0.72,
            "rationale": "Performance optimization: prevent N+1 queries by batch fetching",
            "risk_level": "high",
        }
    ],
}

# Example 4: Multi-option suggestion (extract each option)
EXAMPLE_MULTI_OPTION = {
    "comment": """
The error handling here could be improved. Choose one of these approaches:

**Option 1: Specific exceptions**
```python
try:
    result = api_call()
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
    return None
except TimeoutError as e:
    logger.error(f"Request timed out: {e}")
    return None
```

**Option 2: Generic with re-raise**
```python
try:
    result = api_call()
except Exception as e:
    logger.error(f"API call failed: {e}")
    raise
```

**Option 3: Silent fallback**
```python
try:
    result = api_call()
except Exception:
    return default_value
```

I recommend **Option 1** for production code as it provides better diagnostics.
""",
    "output": [
        {
            "file_path": "src/api_client.py",
            "start_line": 34,
            "end_line": 41,
            "new_content": (
                "try:\n    result = api_call()\n"
                'except ConnectionError as e:\n    logger.error(f"Connection failed: {e}")\n'
                "    return None\nexcept TimeoutError as e:\n"
                '    logger.error(f"Request timed out: {e}")\n    return None'
            ),
            "change_type": "modification",
            "confidence": 0.85,
            "rationale": (
                "Improve error handling with specific exception types " "(recommended option)"
            ),
            "risk_level": "medium",
        },
        {
            "file_path": "src/api_client.py",
            "start_line": 34,
            "end_line": 38,
            "new_content": (
                "try:\n    result = api_call()\n"
                'except Exception as e:\n    logger.error(f"API call failed: {e}")\n'
                "    raise"
            ),
            "change_type": "modification",
            "confidence": 0.85,
            "rationale": (
                "Improve error handling with generic exception and re-raise " "(alternative option)"
            ),
            "risk_level": "medium",
        },
        {
            "file_path": "src/api_client.py",
            "start_line": 34,
            "end_line": 37,
            "new_content": (
                "try:\n    result = api_call()\n" "except Exception:\n    return default_value"
            ),
            "change_type": "modification",
            "confidence": 0.85,
            "rationale": "Improve error handling with silent fallback (alternative option)",
            "risk_level": "medium",
        },
    ],
}

# Example 5: Edge case - discussion only (no changes)
EXAMPLE_NO_CHANGES = {
    "comment": """
**Question about implementation**

I'm not sure if this approach is the best for handling async operations.
Have you considered using asyncio instead of threading?

What are the performance implications of this choice?
""",
    "output": [],  # No actionable code changes
}

# Example 6: Deletion (empty new_content)
EXAMPLE_DELETION = {
    "comment": """
Remove this deprecated function:

```diff
@@ -120,6 +120,0 @@ def old_api():
-def old_api():
-    \"\"\"Deprecated: Use new_api() instead.\"\"\"
-    return legacy_call()
```

This function has been deprecated since v1.0 and should be removed.
""",
    "output": [
        {
            "file_path": "src/api.py",
            "start_line": 120,
            "end_line": 122,
            "new_content": "",
            "change_type": "deletion",
            "confidence": 0.95,
            "rationale": "Remove deprecated function that has been unused since v1.0",
            "risk_level": "medium",
        }
    ],
}

# Example 7: Addition (new code)
EXAMPLE_ADDITION = {
    "comment": """
Add input validation:

```suggestion
def process_user_input(data):
    if not isinstance(data, dict):
        raise ValueError("Input must be a dictionary")
    if "username" not in data:
        raise ValueError("Username is required")

    # Process validated input
    return handle_user(data)
```
""",
    "output": [
        {
            "file_path": "src/handlers.py",
            "start_line": 45,
            "end_line": 52,
            "new_content": (
                "def process_user_input(data):\n    if not isinstance(data, dict):\n"
                '        raise ValueError("Input must be a dictionary")\n'
                '    if "username" not in data:\n'
                '        raise ValueError("Username is required")\n    \n'
                "    # Process validated input\n    return handle_user(data)"
            ),
            "change_type": "addition",
            "confidence": 0.88,
            "rationale": "Add input validation to prevent errors from invalid data",
            "risk_level": "low",
        }
    ],
}

# Aggregate all examples for easy access
ALL_EXAMPLES: dict[str, Any] = {
    "diff_blocks": EXAMPLE_DIFF_BLOCKS,
    "suggestions": EXAMPLE_SUGGESTIONS,
    "natural_language": EXAMPLE_NATURAL_LANGUAGE,
    "multi_option": EXAMPLE_MULTI_OPTION,
    "no_changes": EXAMPLE_NO_CHANGES,
    "deletion": EXAMPLE_DELETION,
    "addition": EXAMPLE_ADDITION,
}
