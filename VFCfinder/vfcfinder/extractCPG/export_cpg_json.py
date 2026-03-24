#!/usr/bin/env python3
"""
自动化导出 Joern CPG 为 JSON 格式
"""

import subprocess
import os
import tempfile
import shutil
import time

def export_cpg_to_json(cpg_bin_path: str, output_json_path: str):
    """
    使用 Joern REPL 导出 CPG 为 JSON
    """
    cpg_bin_path = os.path.abspath(cpg_bin_path)
    output_json_path = os.path.abspath(output_json_path)
    
    # Joern 命令
    joern_cmd = "/home/zhoushaotao/.openclaw/workspace-coder/master/joern-install/joern-cli/joern"
    
    # 检查文件是否存在
    if not os.path.exists(cpg_bin_path):
        raise FileNotFoundError(f"CPG binary not found: {cpg_bin_path}")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    temp_cpg = os.path.join(temp_dir, "cpg.bin")
    shutil.copy(cpg_bin_path, temp_cpg)
    
    try:
        # Joern REPL 命令
        commands = [
            "importCpg(\"" + temp_cpg + "\")",
            "cpg.graph.nodes.map(n => n.toJson()).saveJson(\"" + output_json_path + "\")",
            "exit"
        ]
        
        # 运行 Joern
        process = subprocess.Popen(
            [joern_cmd],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=temp_dir
        )
        
        # 发送命令
        for cmd in commands:
            process.stdin.write(cmd + "\n")
            process.stdin.flush()
            time.sleep(0.5)  # 等待执行
        
        # 等待完成
        stdout, stderr = process.communicate(timeout=180)
        
        print("STDOUT:", stdout[-2000:] if len(stdout) > 2000 else stdout)
        print("STDERR:", stderr[-2000:] if len(stderr) > 2000 else stderr)
        
        # 检查输出
        if os.path.exists(output_json_path):
            print(f"✓ Exported JSON to: {output_json_path}")
            return True
        else:
            print(f"✗ Failed to export JSON")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        # 清理
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    # 第一个仓库的 CPG
    cpg_bin = "/home/zhoushaotao/.openclaw/workspace-coder/master/datasets/joern_cpg/aafwk_aafwk_lite.cpg.bin"
    output_json = "/home/zhoushaotao/.openclaw/workspace-coder/master/datasets/joern_cpg/json/aafwk_aafwk_lite.cpg.json"
    
    # 创建输出目录
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    
    print("Exporting Joern CPG to JSON...")
    success = export_cpg_to_json(cpg_bin, output_json)
    
    if success:
        print("\n✓ Export complete!")
        import json
        with open(output_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"  Nodes: {len(data.get('nodes', []))}")
        print(f"  Edges: {len(data.get('edges', []))}")
    else:
        print("\n✗ Export failed!")
