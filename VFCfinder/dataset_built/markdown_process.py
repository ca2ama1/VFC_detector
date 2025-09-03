#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gitee 链接提取工具

该脚本用于从 OpenHarmony 安全公告的 Markdown 文件中提取 Gitee 的 commit 和 pull request 链接信息，
并生成 CSV 和 JSON 格式的报告。

功能特点：
1. 递归查找指定目录下所有符合 YYYY-MM.md 格式的 Markdown 文件
2. 支持按时间过滤（只处理指定时间及之后的文件）
3. 提取两种类型的 Gitee 链接：
   - Commit 链接（格式：https://gitee.com/openharmony/[repo]/commit/[sha]）
   - Pull Request 链接（格式：https://gitee.com/openharmony/[repo]/pulls/[number]）
4. 自动过滤 "### 以下为三方库漏洞" 之后的内容
5. 生成三种输出文件：
   - commits_summary_nothree.csv - 所有 commit 记录
   - pulls_summary_nothree.csv - 所有 PR 记录
   - all_nothree_data.json - 原始 JSON 数据

使用方法：
基本用法：
  python script.py [目录路径]

带时间过滤的用法：
  python script.py [目录路径] --time YYYY-MM
  或
  python script.py [目录路径] -t YYYY-MM

示例：
  # 处理默认目录下所有文件
  python script.py

  # 处理指定目录下2024年4月及之后的文件
  python script.py /path/to/security_data -t 2024-04

注意事项：
1. 脚本只会处理文件名符合 YYYY-MM.md 格式的文件
2. 时间过滤基于文件名中的时间部分（如 2024-04.md）
3. 脚本会自动忽略 "### 以下为三方库漏洞" 之后的内容
4. 确保有足够的权限读取输入文件和写入输出文件
"""
import os
import re
import csv
import json
import argparse
from typing import Dict, List


def read_markdown_file(file_path: str) -> str:
    """从文件中读取Markdown内容"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def find_markdown_files(directory: str, min_time: str = None) -> List[str]:
    """递归查找目录下所有.md文件，可选按时间过滤，只处理YYYY-MM格式的文件"""
    markdown_files = []
    # 验证YYYY-MM格式的正则表达式
    time_pattern = re.compile(r'^\d{4}-\d{2}\.md$')

    for root, _, files in os.walk(directory):
        for file in files:
            # 只处理符合YYYY-MM.md格式的文件
            if time_pattern.match(file):
                # 如果设置了时间参数，进行过滤
                if min_time:
                    # 提取文件名中的时间部分（如2024-01）
                    time_part = file.split('.')[0]
                    print(time_part)
                    # 只处理该时间及之后的文件
                    if time_part >= min_time:
                        print(os.path.join(root, file))
                        markdown_files.append(os.path.join(root, file))
                else:
                    # 如果没有时间参数，处理所有符合格式的文件
                    markdown_files.append(os.path.join(root, file))
    return markdown_files
def extract_gitee_links(markdown_text: str) -> Dict[str, List[Dict]]:
    """
    从Markdown文本中提取Gitee的commit和pull信息

    Args:
        markdown_text: 包含Gitee链接的Markdown文本

    Returns:
        {
            "commits": [{"repo_url": str, "sha": str}],
            "pulls": [{"owner": str, "repo": str, "number": int, "url": str}]
        }
    """
    # 初始化结果字典
    result = {
        "commits": [],
        "pulls": []
    }
    #只要第三方库之前的内容
    markdown_text = markdown_text.split("### 以下为三方库漏洞")[0]


    # 正则表达式匹配commit链接
    commit_pattern = re.compile(
        r'https://gitee\.com/openharmony/([^/]+)/commit/([0-9a-f]+)'
    )

    # 正则表达式匹配pull链接
    pull_pattern = re.compile(
        r'https://gitee\.com/openharmony/([^/]+)/pulls/(\d+)'
    )

    # 查找所有commit链接
    for match in commit_pattern.finditer(markdown_text):
        repo = match.group(1)
        sha = match.group(2)
        result["commits"].append({
            "repo_url": f"https://gitee.com/openharmony/{repo}",
            "sha": sha
        })

    # 查找所有pull链接
    for match in pull_pattern.finditer(markdown_text):
        repo = match.group(1)
        number = int(match.group(2))
        result["pulls"].append({
            "owner": "openharmony",
            "repo": repo,
            "number": number,
            "url": f"https://gitee.com/openharmony/{repo}/pulls/{number}"
        })

    return result


def save_to_csv(data: List[Dict], filename: str, fieldnames: List[str]):
    """将数据保存为CSV文件"""
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"已保存 {len(data)} 条记录到 {filename}")


def process_directory(directory: str, min_time: str = None):
    """处理目录下所有Markdown文件，可选按时间过滤"""
    all_commits = []
    all_pulls = []

    markdown_files = find_markdown_files(directory, min_time)
    time_info = f"（时间过滤: {min_time}及之后）" if min_time else ""
    print(f"共找到 {len(markdown_files)} 个Markdown文件{time_info}")

    for file_path in markdown_files:
        try:
            markdown_text = read_markdown_file(file_path)
            extracted_data = extract_gitee_links(markdown_text)

            # 添加来源文件信息
            for commit in extracted_data["commits"]:
                commit["source_file"] = os.path.basename(file_path)
                all_commits.append(commit)

            for pull in extracted_data["pulls"]:
                pull["source_file"] = os.path.basename(file_path)
                all_pulls.append(pull)

            print(
                f"处理完成: {file_path} (发现 {len(extracted_data['commits'])} commits, {len(extracted_data['pulls'])} PRs)")

        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {str(e)}")

    # 保存commit数据
    if all_commits:
        commit_fields = ["repo_url", "sha", "source_file"]
        save_to_csv(all_commits, "commits_summary_nothree.csv", commit_fields)
    else:
        print("未发现任何commit记录")

    # 保存PR数据
    if all_pulls:
        pull_fields = ["owner", "repo", "number", "url", "source_file"]
        save_to_csv(all_pulls, "pulls_summary_nothree.csv", pull_fields)
    else:
        print("未发现任何PR记录")

    # 可选：保存原始JSON数据
    with open("all_nothree_data.json", 'w', encoding='utf-8') as f:
        json.dump({"commits": all_commits, "pulls": all_pulls}, f, indent=2)
    print("原始数据已保存到 all_nothree_data.json")


if __name__ == "__main__":
    # 设置命令行参数解析
    parser = argparse.ArgumentParser(description='提取Markdown文件中的Gitee链接')
    parser.add_argument('directory', nargs='?', default='openharmony_security_data',
                        help='要处理的目录路径（默认: openharmony_security_data）')
    parser.add_argument('--time', '-t', type=str,
                        help='可选时间参数，格式为YYYY-MM（如202504），只处理该时间及之后的文档')

    args = parser.parse_args()

    target_directory = args.directory
    min_time = args.time  # 如果没有提供时间参数，这里为None

    if os.path.isdir(target_directory):
        process_directory(target_directory, min_time)
    else:
        print(f"错误: 目录 {target_directory} 不存在")
        print("使用方法: python script.py [目录路径] [--time YYYY-MM]")
