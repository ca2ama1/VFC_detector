"""
负样本生成脚本

该脚本用于从Gitee仓库中收集非漏洞修复的commit作为负样本，与已有的正样本(漏洞修复commit)组成完整的数据集。

主要功能：
1. 从JSON文件加载正样本(漏洞修复commit)
2. 为每个正样本从同一仓库中收集非漏洞修复commit作为负样本
3. 保存负样本数据集

使用说明：
1. 需要设置GITEE_TOKEN环境变量作为API访问令牌
2. 配置输入JSON文件路径和输出文件路径
3. 可调整负样本与正样本的比例(neg_pos_ratio)

输出格式：
每个负样本包含以下字段：
- repo_url: 仓库URL
- sha: commit SHA
- source_file: 来源标记("negative_sample")
- is_positive: 是否为正样本(False)
- matched_positive_sha: 对应的正样本SHA
"""

import json
import time
import requests
import random
import os
from typing import List, Dict
from collections import defaultdict

# ================ 配置参数 ================
# Gitee API配置
GITEE_API_URL = "https://gitee.com/api/v5/repos/{owner}/{repo}/commits"
ACCESS_TOKEN = os.environ.get('GITEE_TOKEN')  # 从环境变量获取API令牌

# 请求设置
REQUEST_DELAY = 1  # 请求延迟(秒)，避免触发API速率限制

# 文件路径配置
INPUT_JSON = "../all_nothree_vul_commit_url_list.json"  # 输入JSON文件路径(正样本)
OUTPUT_JSON = "../all_nothree_nonvul_commit_url_list.json"  # 输出数据集文件路径(负样本)

# 样本比例配置
NEG_POS_RATIO = 1  # 负样本与正样本的比例


def load_positive_commits(json_file: str) -> List[Dict]:
    """
    加载JSON文件中的正样本commit

    Args:
        json_file: JSON文件路径

    Returns:
        正样本commit列表，每个commit是一个字典
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def get_repo_commits(repo_url: str, exclude_shas: List[str], count: int) -> List[Dict]:
    """
    获取仓库的其他commit作为负样本

    Args:
        repo_url: 仓库URL
        exclude_shas: 需要排除的commit sha列表(正样本)
        count: 需要获取的负样本数量

    Returns:
        负样本commit列表，每个commit包含基本信息
    """
    # 从URL中提取owner和repo
    parts = repo_url.split('/')
    owner, repo = parts[-2], parts[-1]

    # 准备API请求参数
    url = GITEE_API_URL.format(owner=owner, repo=repo)
    params = {
        "access_token": ACCESS_TOKEN,
        "per_page": 100  # 每页最大数量
    }

    negative_samples = []
    page = 1
    collected_shas = set(exclude_shas)  # 需要排除的sha集合

    try:
        while len(negative_samples) < count:
            params["page"] = page
            response = requests.get(url, params=params)
            response.raise_for_status()
            commits = response.json()

            if not commits:
                break  # 没有更多commit了

            for commit in commits:
                sha = commit["sha"]
                if sha not in collected_shas:
                    negative_samples.append({
                        "repo_url": repo_url,
                        "sha": sha,
                        "source_file": "negative_sample",
                        "is_positive": False,
                        "matched_positive_sha": None  # 将在后续填充
                    })
                    collected_shas.add(sha)  # 避免重复收集
                    if len(negative_samples) >= count:
                        break

            page += 1
            time.sleep(REQUEST_DELAY)

    except Exception as e:
        print(f"获取仓库 {repo_url} 的commit失败: {str(e)}")

    if len(negative_samples) < count:
        print(f"警告: 仓库 {repo_url} 只有 {len(negative_samples)} 个可用负样本，需要 {count} 个")

    return negative_samples


def generate_negative_samples(positive_commits: List[Dict], ratio: int = 1) -> List[Dict]:
    """
    生成负样本，每个仓库的正样本commit对应ratio个不同的负样本commit

    Args:
        positive_commits: 正样本commit列表
        ratio: 每个正样本对应的负样本数量

    Returns:
        负样本commit列表
    """
    # 按仓库分组正样本
    repo_groups = defaultdict(list)
    for commit in positive_commits:
        repo_url = commit["repo_url"]
        repo_groups[repo_url].append(commit["commit_sha"])

    negative_samples = []

    # 为每个仓库单独处理
    for repo_url, positive_shas in repo_groups.items():
        print(f"\n处理仓库: {repo_url}")
        print(f"正样本数量: {len(positive_shas)}")

        # 获取该仓库的所有可用负样本
        total_negatives_needed = len(positive_shas) * ratio
        repo_negatives = get_repo_commits(repo_url, positive_shas, total_negatives_needed)

        # 如果获取的负样本不足，按实际数量调整比例
        actual_ratio = len(repo_negatives) // len(positive_shas) if positive_shas else 0
        if actual_ratio < ratio:
            print(f"调整比例: 期望 {ratio}:1，实际 {actual_ratio}:1")

        # 为每个正样本分配负样本
        for i, positive_sha in enumerate(positive_shas):
            start_idx = i * ratio
            end_idx = start_idx + ratio
            assigned_negatives = repo_negatives[start_idx:end_idx]

            # 标记这些负样本对应的正样本sha
            for neg in assigned_negatives:
                neg["matched_positive_sha"] = positive_sha

            negative_samples.extend(assigned_negatives)

        print(f"从该仓库获取负样本: {len(repo_negatives)}")

    return negative_samples


def save_dataset(negative: List[Dict], output_file: str):
    """
    保存负样本数据集

    Args:
        negative: 负样本列表
        output_file: 输出文件路径
    """
    # 打乱顺序
    random.shuffle(negative)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(negative, f, indent=2, ensure_ascii=False)

    print(f"\n数据集已保存到 {output_file}")
    print(f"负样本总数: {len(negative)}")


def main():
    """主函数"""
    # 1. 加载正样本
    print("正在加载正样本...")
    positive_commits = load_positive_commits(INPUT_JSON)
    print(f"加载了 {len(positive_commits)} 个正样本commit")
    print(f"涉及 {len(set(c['repo_url'] for c in positive_commits))} 个不同仓库")

    # 2. 生成负样本
    print("\n开始生成负样本...")
    negative_commits = generate_negative_samples(positive_commits, NEG_POS_RATIO)

    # 3. 保存数据集
    save_dataset(negative_commits, OUTPUT_JSON)


if __name__ == "__main__":
    main()

# import json
# import time
# import requests
# import random
# import os
# from typing import List, Dict
# from collections import defaultdict
#
# # Gitee API配置
# GITEE_API_URL = "https://gitee.com/api/v5/repos/{owner}/{repo}/commits"
# ACCESS_TOKEN = os.environ.get('GITEE_TOKEN')
#
# REQUEST_DELAY = 1  # 请求延迟(秒)，避免触发API速率限制
#
#
# def load_positive_commits(json_file: str) -> List[Dict]:
#     """加载JSON文件中的正样本commit"""
#     with open(json_file, 'r', encoding='utf-8') as f:
#         data = json.load(f)
#     return data
#
#
# def get_repo_commits(repo_url: str, exclude_shas: List[str], count: int) -> List[Dict]:
#     """
#     获取仓库的其他commit作为负样本
#
#     Args:
#         repo_url: 仓库URL
#         exclude_shas: 需要排除的commit sha列表(正样本)
#         count: 需要获取的负样本数量
#
#     Returns:
#         负样本commit列表
#     """
#     # 从URL中提取owner和repo
#     parts = repo_url.split('/')
#     owner, repo = parts[-2], parts[-1]
#
#     # 准备API请求
#     url = GITEE_API_URL.format(owner=owner, repo=repo)
#     params = {
#         "access_token": ACCESS_TOKEN,
#         "per_page": 100  # 每页最大数量
#     }
#
#     negative_samples = []
#     page = 1
#     collected_shas = set(exclude_shas)  # 需要排除的sha集合
#
#     try:
#         while len(negative_samples) < count:
#             params["page"] = page
#             response = requests.get(url, params=params)
#             response.raise_for_status()
#             commits = response.json()
#
#             if not commits:
#                 break  # 没有更多commit了
#
#             for commit in commits:
#                 sha = commit["sha"]
#                 if sha not in collected_shas:
#                     negative_samples.append({
#                         "repo_url": repo_url,
#                         "sha": sha,
#                         "source_file": "negative_sample",
#                         "is_positive": False,
#                         "matched_positive_sha": None  # 将在后续填充
#                     })
#                     collected_shas.add(sha)  # 避免重复收集
#                     if len(negative_samples) >= count:
#                         break
#
#             page += 1
#             time.sleep(REQUEST_DELAY)
#
#     except Exception as e:
#         print(f"获取仓库 {repo_url} 的commit失败: {str(e)}")
#
#     if len(negative_samples) < count:
#         print(f"警告: 仓库 {repo_url} 只有 {len(negative_samples)} 个可用负样本，需要 {count} 个")
#
#     return negative_samples
#
#
# def generate_negative_samples(positive_commits: List[Dict], ratio: int = 1) -> List[Dict]:
#     """
#     生成负样本，每个仓库的正样本commit对应ratio个不同的负样本commit
#
#     Args:
#         positive_commits: 正样本commit列表
#         ratio: 每个正样本对应的负样本数量
#
#     Returns:
#         负样本commit列表
#     """
#     # 按仓库分组正样本
#     repo_groups = defaultdict(list)
#     for commit in positive_commits:
#         repo_url = commit["repo_url"]
#         repo_groups[repo_url].append(commit["commit_sha"])
#
#     negative_samples = []
#
#     # 为每个仓库单独处理
#     for repo_url, positive_shas in repo_groups.items():
#         print(f"\n处理仓库: {repo_url}")
#         print(f"正样本数量: {len(positive_shas)}")
#
#         # 获取该仓库的所有可用负样本
#         total_negatives_needed = len(positive_shas) * ratio
#         repo_negatives = get_repo_commits(repo_url, positive_shas, total_negatives_needed)
#
#         # 如果获取的负样本不足，按实际数量调整比例
#         actual_ratio = len(repo_negatives) // len(positive_shas) if positive_shas else 0
#         if actual_ratio < ratio:
#             print(f"调整比例: 期望 {ratio}:1，实际 {actual_ratio}:1")
#
#         # 为每个正样本分配负样本
#         for i, positive_sha in enumerate(positive_shas):
#             start_idx = i * ratio
#             end_idx = start_idx + ratio
#             assigned_negatives = repo_negatives[start_idx:end_idx]
#
#             # 标记这些负样本对应的正样本sha
#             for neg in assigned_negatives:
#                 neg["matched_positive_sha"] = positive_sha
#
#             negative_samples.extend(assigned_negatives)
#
#         print(f"从该仓库获取负样本: {len(repo_negatives)}")
#
#     return negative_samples
#
#
# def save_dataset(negative: List[Dict], output_file: str):
#     """保存负样本数据集"""
#     # 打乱顺序
#     random.shuffle(negative)
#
#     with open(output_file, 'w', encoding='utf-8') as f:
#         json.dump(negative, f, indent=2, ensure_ascii=False)
#
#     print(f"\n数据集已保存到 {output_file}")
#     print(f"负样本总数: {len(negative)}")
#
#
# def main():
#     # 参数设置
#     input_json = "../all_nothree_vul_commit_url_list.json"  # 输入JSON文件路径
#     output_json = "../all_nothree_nonvul_commit_url_list.json"  # 输出数据集文件路径
#     neg_pos_ratio = 1  # 负样本与正样本的比例
#
#     # 1. 加载正样本
#     print("正在加载正样本...")
#     positive_commits = load_positive_commits(input_json)
#     print(f"加载了 {len(positive_commits)} 个正样本commit")
#     print(f"涉及 {len(set(c['repo_url'] for c in positive_commits))} 个不同仓库")
#
#     # 2. 生成负样本
#     print("\n开始生成负样本...")
#     negative_commits = generate_negative_samples(positive_commits, neg_pos_ratio)
#
#     # 3. 保存数据集
#     save_dataset(negative_commits, output_json)
#
#
# if __name__ == "__main__":
#     main()
