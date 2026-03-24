# Joern CPG to CodeQL Converter

This tool converts Joern CPG JSON to CodeQL-compatible SQLite database format.

## Usage

### Step 1: Generate Joern CPG

```bash
joern --run dumpcpg14 --src /path/to/source --output /path/to/cpg
# 或者使用更快的 c2cpg.sh
/home/zhoushaotao/.openclaw/workspace-coder/master/joern-install/joern-cli/c2cpg.sh --output /path/to/cpg.bin /path/to/source
```

### Step 2: Export CPG to JSON

```bash
# 在 Joern REPL 中
joern> importCpg("/path/to/cpg.bin")
joern> saveCpgAsJson("/path/to/cpg.json")
joern> exit
```

### Step 3: Convert to CodeQL Database

```bash
python3 convert.py --input /path/to/cpg.json --output /path/to/output.db
```

### Step 4: Analyze with CodeQL

```bash
codeql database analyze /path/to/output.db \
    /path/to/queries/cpg-calls-cross-file.ql \
    --format=csv \
    --output=/path/to/results.csv
```

## Integration Scripts

- `convert_and_analyze.sh` - End-to-end conversion and analysis
- `batch_convert.sh` - Batch convert multiple CPG files

## Notes

- This is a simplified converter - for full features, consider using CodeQL's native extractors
- Cross-file analysis requires resolving function definitions across files
