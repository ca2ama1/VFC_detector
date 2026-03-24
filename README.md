# VFC_detector

## Overview

VFC_detector is a vulnerability fix commit and branch localization tool for open-source code repositories. It detects vulnerability fix commits and identifies the affected branches, helping developers quickly locate and understand security patches.

## Features

### Core Functionality

- **Vulnerability Fix Commit Detection**: Automatically identifies commits that fix security vulnerabilities
- **Branch Localization**: Precisely locates which branches contain vulnerability fixes
- **Code Property Graph (CPG) Analysis**: Uses GraphSPD-inspired approach to extract code structure
- **Open-source Repository Support**: Works with GitHub, GitLab, and other popular platforms

### Branch Localization Capabilities

- **Branch Tracing**: Tracks vulnerability fixes across different branches
- **Merge Commit Analysis**: Identifies when fixes are merged from one branch to another
- **Branch Impact Assessment**: Determines which branches are affected by specific vulnerabilities
- **History Reconstruction**: Reconstructs the propagation of fixes through the repository history

## Technical Architecture

### Data Flow

```
Repository → Commit Analysis → CPG Extraction → Vulnerability Detection → Branch Localization → Results
```

### Key Components

1. **Commit Analyzer**
    - Parses commit messages and diffs
    - Identifies security-related keywords and patterns
    - Extracts code changes for further analysis
2. **CPG Builder**
    - Constructs Code Property Graphs from source code
    - Analyzes control flow and data dependencies
    - References GraphSPD's approach for graph construction
3. **Vulnerability Detector**
    - Applies pattern matching for known vulnerability signatures
    - Uses machine learning models for anomaly detection
    - Validates findings against vulnerability databases
4. **Branch Locator**
    - Analyzes Git history and branch structure
    - Tracks commit propagation across branches
    - Identifies merge points and cherry-picked commits

## Installation

```
# Clone the repository
git clone https://github.com/ca2ama1/VFC_detector.git
cd VFC_detector

# Install dependencies
pip install -r requirements.txt

# Set up configuration
cp config.example.yaml config.yaml
```

## Usage

### Basic Usage

```
from vfc_detector import VFCAnalyzer

# Initialize analyzer
analyzer = VFCAnalyzer("path/to/repository")

# Detect vulnerability fix commits
fix_commits = analyzer.detect_fix_commits()

# Locate affected branches
branch_locations = analyzer.locate_branches(fix_commits)

# Generate report
report = analyzer.generate_report()
```

### Command Line Interface

```
# Analyze a repository
python vfc_detector.py analyze --repo /path/to/repo --output report.json

# List vulnerable branches
python vfc_detector.py branches --repo /path/to/repo

# Generate detailed report
python vfc_detector.py report --repo /path/to/repo --format html
```

## Configuration

### Configuration File (`config.yaml`)

```
# Repository settings
repository:
  path: "/path/to/analyze"
  type: "git"  # git, github, gitlab

# Analysis settings
analysis:
  # Vulnerability detection settings
  vulnerability_detection:
    enable_ml: true
    confidence_threshold: 0.8
    
  # Branch localization settings
  branch_localization:
    max_depth: 10
    include_merged: true
    track_cherry_picks: true
    
  # CPG extraction settings
  cpg_extraction:
    language: "java"  # java, python, c, cpp
    max_memory: "2G"

# Output settings
output:
  format: "json"
  verbose: true
```

## Branch Localization Examples

### Example 1: Basic Branch Tracing

```
# Find which branches contain a specific fix
fix_commit = "abc123"
affected_branches = analyzer.find_affected_branches(fix_commit)
print(f"Fix {fix_commit} affects branches: {affected_branches}")
```

### Example 2: Merge Commit Analysis

```
# Analyze how a fix propagates through merges
fix_commit = "def456"
merge_analysis = analyzer.analyze_merge_propagation(fix_commit)
print(f"Merge propagation path: {merge_analysis['path']}")
print(f"Affected branches count: {merge_analysis['branch_count']}")
```

### Example 3: Branch Impact Report

```
# Generate comprehensive branch impact report
report = analyzer.generate_branch_impact_report()
for branch, details in report.items():
    print(f"Branch: {branch}")
    print(f"  Vulnerable: {details['vulnerable']}")
    print(f"  Fix Commit: {details['fix_commit']}")
    print(f"  Fix Date: {details['fix_date']}")
```

## Output Format

### Vulnerability Fix Commit Format

```
{
  "commit_hash": "abc123...",
  "author": "username",
  "date": "2024-01-01T12:00:00Z",
  "message": "Fix: Buffer overflow in input processing",
  "files_changed": [
    "src/vulnerable.c",
    "tests/test_vulnerable.c"
  ],
  "vulnerability_type": "buffer_overflow",
  "severity": "high",
  "branches": [
    "main",
    "develop",
    "release/v1.2"
  ],
  "merge_points": [
    {
      "branch": "develop",
      "merge_commit": "merge_abc123",
      "date": "2024-01-02T10:00:00Z"
    }
  ]
}
```

## Integration with CI/CD

### GitHub Actions Example

```
name: Vulnerability Detection
on: [push, pull_request]

jobs:
  vfc-detection:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.8'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run VFC_detector
      run: |
        python vfc_detector.py analyze --repo . --output security_report.json
    
    - name: Upload report
      uses: actions/upload-artifact@v2
      with:
        name: security-report
        path: security_report.json
```

## Performance Considerations

### Large Repository Optimization

- **Incremental Analysis**: Only analyze new commits since last run
- **Parallel Processing**: Process multiple files/commits concurrently
- **Memory Management**: Configure appropriate memory limits for CPG extraction
- **Caching**: Cache intermediate results to avoid redundant computations

### Branch Localization Performance

- **Depth Limiting**: Set reasonable limits on branch traversal depth
- **Selective Analysis**: Focus on active branches rather than all historical branches
- **Indexing**: Create indexes on commit history for faster branch queries


---

*VFC_detector: Empowering developers to quickly locate and understand vulnerability fixes in open-source projects.*

