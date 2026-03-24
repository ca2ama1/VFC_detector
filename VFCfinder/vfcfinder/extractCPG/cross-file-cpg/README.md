# Cross-File Function Calls - CodeQL 查询

This directory contains CodeQL queries for analyzing cross-file function calls.

## Files

- `cpg-calls-cross-file.ql` - The main query to find cross-file function calls
- `qlpack.yml` - QL pack configuration

## Usage

### For C/C++

```bash
# Build database
codeql database create /path/to/db --language=cpp --source-root=/path/to/source

# Run query
codeql database analyze /path/to/db ./cpg-calls-cross-file.ql --format=csv --output=/path/to/output.csv

# Or run with output in SARIF format
codeql database analyze /path/to/db ./cpg-calls-cross-file.ql --format=sarif-latest --output=/path/to/output.sarif
```

### For Other Languages

You can modify the query for other languages:
- Java: Change `import cpp` to `import java`
- Python: Change `import cpp` to `import python`
- JavaScript: Change `import cpp` to `import javascript`

## Joern Integration

To integrate with Joern CPG:

1. Generate Joern CPG for your codebase
2. Export CPG to a format CodeQL can read (e.g., JSON)
3. Write a custom extractor to convert Joern CPG to CodeQL database format

Example workflow:

```bash
# Step 1: Generate Joern CPG
joern --run dumpcpg14 --src /path/to/source --output /path/to/cpg

# Step 2: Convert Joern CPG to CodeQL database
# (requires custom converter script)

# Step 3: Run CodeQL query
codeql database analyze /path/to/db ./cpg-calls-cross-file.ql
```

## Cross-Language Support

This setup supports:
- **Java**
- **Python**
- **JavaScript/TypeScript**
- **C/C++**
- **Go**
- **C#**
- **Ruby**
- **Swift**
- And more...

Each language has its own query file (e.g., `cpg-calls-cross-file-java.ql`, etc.)
