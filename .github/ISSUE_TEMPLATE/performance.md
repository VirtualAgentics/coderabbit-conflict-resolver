---
name: Performance Issue
about: Report performance problems or request performance improvements
title: '[PERFORMANCE] '
labels: performance
assignees: ''
---

## Performance Issue

### Description

Describe the performance issue or improvement request.

### Current Performance

What is the current performance?

* **Execution time**: [e.g., 5 seconds]
* **Memory usage**: [e.g., 500MB]
* **CPU usage**: [e.g., 80%]
* **Throughput**: [e.g., 10 operations/second]

### Expected Performance

What performance do you expect or need?

* **Execution time**: [e.g., 1 second]
* **Memory usage**: [e.g., 100MB]
* **CPU usage**: [e.g., 20%]
* **Throughput**: [e.g., 100 operations/second]

### Environment

* **OS**: [e.g., Ubuntu 22.04, Windows 11, macOS 13.0]
* **Python Version**: [e.g., 3.12.0]
* **Package Version**: [e.g., 0.1.0]
* **Hardware**: [e.g., 8GB RAM, 4 CPU cores]
* **Data Size**: [e.g., 1000 files, 50MB total]

### Steps to Reproduce

1. Set up test data: [describe]
2. Run the operation: [describe]
3. Measure performance: [describe]
4. Observe the issue: [describe]

### Code Example

```python
# Provide a minimal code example that demonstrates the performance issue
from review_bot_automator import ConflictResolver

# Your code here

```

### Profiling Results

If you've done any profiling, please include the results:

```bash
# Example profiling command and output
python -m cProfile -o profile.stats your_script.py

```

### Benchmark Results

If you have benchmark results, please include them:

```bash
# Example benchmark command and output
time python your_script.py

```

### Performance Bottlenecks

Where do you think the performance bottleneck is?

* [ ] File I/O operations
* [ ] Network requests (GitHub API)
* [ ] Conflict detection algorithms
* [ ] Memory usage/leaks
* [ ] CPU-intensive computations
* [ ] Database operations
* [ ] Other (please specify)

### Impact

How does this performance issue impact you?

* [ ] Blocks development workflow
* [ ] Causes timeouts
* [ ] Consumes excessive resources
* [ ] Poor user experience
* [ ] Other (please specify)

### Proposed Solutions

If you have ideas for improving performance, please describe them:

### Additional Context

Add any other context about the performance issue here.

### Checklist

* [ ] I have provided specific performance metrics
* [ ] I have included steps to reproduce
* [ ] I have provided a minimal code example
* [ ] I have described the impact
* [ ] I have checked for existing performance issues
