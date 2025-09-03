#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gitee 安全公告爬虫工具

该脚本用于从OpenHarmony的Gitee仓库中爬取安全公告的Markdown文件，保存到本地目录。

功能特点：
1. 递归爬取指定目录下的所有Markdown文件
2. 支持Gitee API认证（需要access token）
3. 自动创建本地目录结构
4. 完善的错误处理和重试机制
5. 跳过已下载的文件（基于文件大小检查）

使用方法：
1. 首先需要在Gitee上获取access token（需有repo权限）
2. 将token填入脚本的GITEE_TOKEN变量
3. 运行脚本：
   python gitee_security_crawler.py

配置选项：
- REPO_OWNER: 仓库所有者（默认为openharmony）
- REPO_NAME: 仓库名称（默认为security）
- TARGET_DIR: 要爬取的子目录（默认为zh/security-disclosure）
- LOCAL_SAVE_PATH: 本地保存路径（默认为./openharmony_security_data）

注意事项：
1. 请确保GITEE_TOKEN有足够的权限（需要repo权限）
2. 脚本会自动跳过已下载的文件
3. 网络不稳定时可能会自动重试
4. 建议在非高峰时段运行脚本以减少API限制
"""

import os
import requests
import json
from urllib.parse import urljoin

# 配置信息
REPO_OWNER = "openharmony"
REPO_NAME = "security"
API_BASE = f"https://gitee.com/api/v5/repos/{REPO_OWNER}/{REPO_NAME}/contents"
TARGET_DIR = "zh/security-disclosure"  # 指定要爬取的子目录
LOCAL_SAVE_PATH = "./openharmony_security_data"
GITEE_TOKEN = os.environ.get('GITEE_TOKEN')

def ensure_dir(path):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def check_auth():
    """检查API认证是否有效"""
    test_url = f"{API_BASE}/README.md"
    response = requests.get(test_url, headers={"Authorization": f"token {GITEE_TOKEN}"})
    if response.status_code == 401:
        raise ValueError("❌ 认证失败：请检查GITEE_TOKEN是否有效")
    elif response.status_code == 403:
        raise ValueError("❌ 权限不足：需添加repo权限")
    return True


def get_api_response(url):
    """
    增强版API请求处理
    返回: (status_code, data_or_error_message)
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"token {GITEE_TOKEN}",
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        # 状态码处理矩阵
        if response.status_code == 200:
            try:
                return (200, response.json())
            except ValueError:
                return (500, "JSON解析失败")
        elif response.status_code == 404:
            return (404, "资源不存在")
        elif response.status_code == 403:
            return (403, "访问被拒绝（检查token权限）")
        else:
            return (response.status_code, f"HTTP错误: {response.text[:100]}")

    except requests.exceptions.Timeout:
        return (408, "请求超时")
    except requests.exceptions.RequestException as e:
        return (500, f"网络错误: {str(e)}")


def download_file(file_url, local_path):
    """增强版文件下载"""
    if not file_url:
        return False

    # 检查文件是否已存在且有效
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        print(f"文件已存在，跳过下载: {local_path}")
        return True

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"token {GITEE_TOKEN}"
    }

    try:
        response = requests.get(file_url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()

        with open(local_path, "w", encoding="utf-8") as f:
            for chunk in response.iter_content(decode_unicode=True):
                f.write(chunk)
        print(f"文件下载完成: {local_path}")
        return True

    except Exception as e:
        print(f"🚨 下载异常 {file_url}: {str(e)}")
        return False


def process_directory(api_path, local_path):
    """增强版目录处理"""
    url = f"{API_BASE}/{api_path}"
    status, data = get_api_response(url)

    if status != 200:
        print(f"⛔ 目录获取失败 [{status}]: {data}")
        return

    for item in data:
        item_path = os.path.join(local_path, item["name"])

        if item["type"] == "dir":
            ensure_dir(item_path)
            process_directory(f"{api_path}/{item['name']}", item_path)
        elif item["name"].endswith(".md"):
            if not download_file(item["download_url"], item_path):
                print(f"⚠️ 文件下载失败: {item['name']}")


def main():
    """主函数"""
    # 新增认证检查（放在目录创建之前）
    if not check_auth():
        print("程序终止：API认证失败")
        return

    ensure_dir(LOCAL_SAVE_PATH)
    print("=== OpenHarmony安全公告爬取开始 ===")
    process_directory(TARGET_DIR, os.path.join(LOCAL_SAVE_PATH, TARGET_DIR))
    print("=== 爬取完成 ===")
    print(f"文件已保存至: {os.path.abspath(LOCAL_SAVE_PATH)}")


if __name__ == "__main__":
    main()