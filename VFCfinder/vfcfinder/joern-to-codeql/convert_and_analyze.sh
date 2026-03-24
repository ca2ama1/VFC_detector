#!/bin/bash
# Joern CPG 转换为 CodeQL 数据库

set -e

JOERN_TO_CODEQL="/home/zhoushaotao/.openclaw/workspace-coder/master/tools/codeql/joern-to-codeql/convert.py"
INPUT_CPG_JSON="/home/zhoushaotao/.openclaw/workspace-coder/master/datasets/joern_cpg/aafwk_aafwk_lite.cpg.json"
OUTPUT_DB="/home/zhoushaotao/.openclaw/workspace-coder/master/datasets/codeql_db/aafwk_aafwk_lite.db"

# 创建输出目录
mkdir -p "$(dirname $OUTPUT_DB)"

# 转换
python3 "$JOERN_TO_CODEQL" --input "$INPUT_CPG_JSON" --output "$OUTPUT_DB"

# 分析
/home/zhoushaotao/.openclaw/workspace-coder/master/tools/codeql/codeql/codeql database analyze "$OUTPUT_DB" \
    /home/zhoushaotao/.openclaw/workspace-coder/master/tools/codeql/cross-file-cpg/cpg-calls-cross-file.ql \
    --format=csv \
    --output=/home/zhoushaotao/.openclaw/workspace-coder/master/datasets/codeql_db/results.csv

echo "Analysis complete!"
