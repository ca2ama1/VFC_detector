# !/usr/bin/env python3
"""
Gitee PR转Commit信息提取工具

使用示例：
    # 使用默认配置运行
    python3 gitee_pr_processor.py

    # 使用自定义参数运行
    python3 gitee_pr_processor.py \
        --input ./data/input/custom_input.json \
        --output ./data/output/custom_output.json \
        --token your_gitee_token_here
"""

import os
import requests
import json
import time
import argparse
from typing import Dict, List, Optional

# ====================== 用户配置区域 (按需修改) ======================
# API基础配置
GITEE_API_BASE = "https://gitee.com/api/v5"  # Gitee API基础地址
REPO_OWNER = "openharmony"  # 仓库所有者名称

# 默认文件路径配置
DEFAULT_INPUT_FILE = "./data/input/all_nothree_data.json"  # 默认输入文件路径
DEFAULT_OUTPUT_FILE = "./data/output/all_nothree_commit_url_list.json"  # 默认输出文件路径

DEFAULT_TOKEN = os.environ.get('GITEE_TOKEN')


# 请求控制参数
REQUEST_DELAY = 0.5  # 请求间隔时间(秒)，防止API限流
TIMEOUT = 10  # 请求超时时间(秒)


# ====================== 主程序逻辑======================

class GiteeAPI:
    """Gitee API操作封装类 """

    def __init__(self, token: str):
        """初始化API客户端"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GiteePRProcessor/1.0",
            "Authorization": f"token {token}",
            "Accept": "application/json"
        })

    def get_commit_info_from_pull(self, repo: str, pull_number: int) -> Optional[Dict]:
        """
        从PR获取commit信息
        :param repo: 仓库名称
        :param pull_number: PR编号
        :return: 包含commit信息的字典或None
        """
        url = f"{GITEE_API_BASE}/repos/{REPO_OWNER}/{repo}/pulls/{pull_number}/commits"

        try:
            response = self.session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            commits = response.json()

            if commits and len(commits) > 0:
                latest_commit = commits[-1]  # 获取最新的commit
                return {
                    "sha": latest_commit['sha'],
                    "url": latest_commit['html_url'],
                    "message": latest_commit['commit']['message'],
                    "author": latest_commit['commit']['author']['name'],
                    "date": latest_commit['commit']['author']['date']
                }
        except requests.exceptions.RequestException as e:
            print(f"获取commit信息失败 {repo}/pulls/{pull_number}: {e}")
        return None

    def get_pull_request_info(self, repo: str, pull_number: int) -> Optional[Dict]:
        """
        获取PR详细信息
        :param repo: 仓库名称
        :param pull_number: PR编号
        :return: 包含PR信息的字典或None
        """
        url = f"{GITEE_API_BASE}/repos/{REPO_OWNER}/{repo}/pulls/{pull_number}"

        try:
            response = self.session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"获取PR信息失败 {repo}/pulls/{pull_number}: {e}")
        return None


def process_pulls_to_commits(input_file: str, output_file: str, token: str):
    """
    处理PR数据并提取commit信息

    处理流程：
    1. 读取输入的PR数据
    2. 逐个获取PR和commit信息
    3. 保存处理结果

    Args:
        input_file: 输入JSON文件路径
        output_file: 输出JSON文件路径
        token: Gitee访问令牌
    """
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # 读取输入文件
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pulls = data.get('pulls', [])
    results = []
    api = GiteeAPI(token)

    print(f"开始处理 {len(pulls)} 个PR请求...")

    for i, pull in enumerate(pulls, 1):
        repo = pull['repo']
        pull_number = pull['number']
        print(f"[{i}/{len(pulls)}] 正在处理 {repo}/pulls/{pull_number}")

        # 获取PR信息
        pr_info = api.get_pull_request_info(repo, pull_number)
        if not pr_info:
            continue

        # 获取commit信息
        commit_info = api.get_commit_info_from_pull(repo, pull_number)
        if not commit_info:
            continue

        # 构建结果字典
        result = {
            "repo": repo,
            "repo_url": f"https://gitee.com/{REPO_OWNER}/{repo}",
            "pull_number": pull_number,
            "pull_url": pull['url'],
            "pull_title": pr_info.get('title', ''),
            "pull_state": pr_info.get('state', ''),
            "pull_created_at": pr_info.get('created_at', ''),
            "pull_merged_at": pr_info.get('merged_at', ''),
            "commit_sha": commit_info['sha'],
            "commit_url": commit_info['url'],
            "commit_message": commit_info['message'],
            "commit_author": commit_info['author'],
            "commit_date": commit_info['date'],
            "source_file": pull.get('source_file', '')
        }
        results.append(result)

        # 保持与原代码相同的请求间隔
        time.sleep(REQUEST_DELAY)

    # 保存结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)

    print(f"\n处理完成！结果已保存到: {output_file}")
    print(f"成功处理: {len(results)}/{len(pulls)} 个PR")


def parse_args():
    """解析命令行参数 """
    parser = argparse.ArgumentParser(description='从Gitee PR提取commit信息')
    parser.add_argument('--input', default=DEFAULT_INPUT_FILE, help='输入JSON文件路径')
    parser.add_argument('--output', default=DEFAULT_OUTPUT_FILE, help='输出JSON文件路径')
    parser.add_argument('--token', default=DEFAULT_TOKEN, help='Gitee访问令牌')
    return parser.parse_args()


def main():
    """主函数 """
    args = parse_args()

    # API认证检查
    api = GiteeAPI(args.token)
    test_url = f"{GITEE_API_BASE}/user"
    try:
        response = api.session.get(test_url)
        if response.status_code == 200:
            print("✅ Gitee API认证成功")
        else:
            print(f"❌ Gitee API认证失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 连接Gitee API失败: {e}")
        return

    # 执行处理流程 (与原逻辑一致)
    process_pulls_to_commits(args.input, args.output, args.token)


if __name__ == "__main__":
    main()