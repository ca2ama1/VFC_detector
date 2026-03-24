#!/bin/bash
# 将 Joern CPG (.cpg.bin) 导出为 JSON 格式

set -e

JOERN_BIN="/home/zhoushaotao/.openclaw/workspace-coder/master/joern-install/joern-cli/joern"

INPUT_DIR="/home/zhoushaotao/.openclaw/workspace-coder/master/datasets/joern_cpg"
OUTPUT_JSON_DIR="/home/zhoushaotao/.openclaw/workspace-coder/master/datasets/joern_cpg/json"

# 创建输出目录
mkdir -p "$OUTPUT_JSON_DIR"

echo "Converting Joern CPG to JSON format..."
echo "Input: $INPUT_DIR"
echo "Output: $OUTPUT_JSON_DIR"

# 遍历所有 .cpg.bin 文件
for cpg_file in "$INPUT_DIR"/*.cpg.bin; do
    if [ ! -f "$cpg_file" ]; then
        continue
    fi
    
    cpg_name=$(basename "$cpg_file" .cpg.bin)
    json_output="$OUTPUT_JSON_DIR/${cpg_name}.cpg.json"
    
    echo ""
    echo "========================================"
    echo "Converting: $cpg_name"
    echo "========================================"
    
    # 检查是否已经转换过
    if [ -f "$json_output" ]; then
        echo "Already converted: $json_output"
        continue
    fi
    
    # 使用 joern --run dumpcpg14 导出 JSON
    # 注意：Joern 4.x 不直接支持输出 JSON，需要使用 joern --export
    # 创建临时目录
    temp_dir=$(mktemp -d)
    cp "$cpg_file" "$temp_dir/"
    
    # 运行 joern 并导出
    echo "Running joern export..."
    
    # Joern 4.x 的导出命令
    "$JOERN_BIN" --export "$temp_dir/cpg.json" "$temp_dir/cpg.bin"
    
    # 检查输出
    if [ -f "$temp_dir/cpg.json" ]; then
        cp "$temp_dir/cpg.json" "$json_output"
        echo "✓ Exported: $json_output"
    else
        echo "✗ Failed to export: $json_output"
    fi
    
    # 清理
    rm -rf "$temp_dir"
done

echo ""
echo "Complete!"
