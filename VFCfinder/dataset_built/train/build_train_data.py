import argparse
import logging
import pandas as pd
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import sys
import time
from typing import List
from pathlib import Path
from git.exc import GitCommandError
from transformers import AutoTokenizer
import re
from datasets import load_dataset, Dataset, concatenate_datasets



# tokenizer = AutoTokenizer.from_pretrained("codebert-base")
tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
import json
# 添加项目路径
sys.path.append("/home/zhoushaotao/home/VFCfinder-main")
from vfcfinder.utils import git_helper


import json
from datetime import datetime


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# 配置日志（保持不变）
def setup_logging(log_file='commit_diff_nonvul_processor.log'):
    """配置日志记录，同时输出到控制台和文件"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger()


logger = setup_logging()

# 定义预期的列名（保持不变）
FULL_COLUMN_NAMES = [
    'sha', 'message', 'file_name', 'file_number', 'file_extension',
    'total_files_changed', 'raw_file_patch', 'patch_number', 'total_patches',
    'raw_patch_header', 'raw_patch', 'original_code', 'original_line_start',
    'original_line_length', 'original_line_end', 'modified_code',
    'modified_line_start', 'modified_line_length', 'modified_line_end',
    'additions', 'added_code', 'deletions', 'deleted_code', 'changes', 'status',
    'total_file_additions', 'total_file_deletions', 'total_file_changes',
    'commit_author_name', 'commit_author_login', 'commit_author_email',
    'commit_author_date', 'commit_committer_name', 'commit_committer_login',
    'commit_committer_email', 'commit_committer_date', 'commit_tree_sha',
    'commit_tree_url', 'commit_verification_verified', 'commit_verification_reason',
    'parents'
]


# 验证函数（保持不变）
def validate_diff_data(diff_data):
    """验证 diff_data 是否包含所有 FULL_COLUMN_NAMES 的字段"""
    if not isinstance(diff_data, (list, dict)):
        logger.error("Diff data is not in expected format (list or dict)")
        return False
    if isinstance(diff_data, list):
        for item in diff_data:
            if not isinstance(item, dict):
                logger.error("Item in diff_data is not a dictionary")
                return False
            missing_fields = set(FULL_COLUMN_NAMES) - set(item.keys())
            if missing_fields:
                logger.error(f"Diff item missing required columns: {missing_fields}")
                return False
        return True
    elif isinstance(diff_data, dict):
        missing_fields = set(FULL_COLUMN_NAMES) - set(diff_data.keys())
        if missing_fields:
            logger.error(f"Diff data missing required columns: {missing_fields}")
            return False
        return True
    return False


# 克隆和diff获取函数（保持不变）
def clone_with_retry(repo_owner, repo_name, clone_path, max_retries=3, retry_delay=5):
    """带重试机制的仓库克隆函数"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries}: Cloning {repo_owner}/{repo_name}")
            git_helper.clone_repo(
                repo_type="github",
                repo_owner=repo_owner,
                repo_name=repo_name,
                clone_path=clone_path
            )
            return True
        except GitCommandError as e:
            logger.error(f"Clone failed: {str(e)}")
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay * (attempt + 1))
    return False


def git_diff_with_retry(clone_path, commit_sha, max_retries=3, retry_delay=2):
    """带重试机制的diff获取函数"""
    for attempt in range(max_retries):
        try:
            diff = git_helper.git_diff(clone_path=clone_path, commit_sha=commit_sha)
            if diff is not None and validate_diff_data(diff):
                return diff
            else:
                logger.warning(f"Diff data for {commit_sha[:7]} is invalid")
                return None
        except Exception as e:
            logger.error(f"Error getting diff for {commit_sha[:7]}: {str(e)}")
            if attempt == max_retries - 1:
                return None
            time.sleep(retry_delay * (attempt + 1))
    return None


# 读取commit URLs（保持不变）
def read_commit_urls_from_file(file_path):
    """读取commit URLs（自动去除换行符）"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            return [line.strip() for line in file if line.strip()]
    except Exception as e:
        logger.error(f"Error reading commit URLs file: {str(e)}")
        raise


# 修改：检查commit是否已处理（JSON格式）
def is_commit_processed(output_path, repo_owner, repo_name, commit_sha):
    """检查该commit是否已经处理过（基于JSON文件）"""
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        return False

    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return any(
                item.get('repo_owner') == repo_owner and
                item.get('repo_name') == repo_name and
                item.get('commit_sha') == commit_sha
                for item in data
            )
    except json.JSONDecodeError:
        return False
    except Exception as e:
        logger.error(f"Error checking existing commits: {str(e)}")
        return False



def safe_read_json(file_path):
    """安全读取可能损坏的JSON文件"""
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning(f"JSON file {file_path} is corrupted, attempting recovery...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                last_brace = content.rfind(']')
                if last_brace > 0:
                    content = content[:last_brace] + ']'
                    return json.loads(content)
        except Exception:
            logger.error("Recovery failed, starting with empty data")
            return []
    except Exception as e:
        logger.error(f"Error reading JSON file: {str(e)}")
        return []


def append_to_json(output_path, new_data):
    """安全追加数据到JSON文件"""
    try:
        existing_data = safe_read_json(output_path)

        if isinstance(new_data, dict):
            existing_data.append(new_data)
        elif isinstance(new_data, list):
            existing_data.extend(new_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)

        current_count = len(existing_data)
        logger.info(f"Appended data, current total items: {current_count}")
        return True, current_count
    except Exception as e:
        logger.error(f"Error writing to JSON: {str(e)}", exc_info=True)
        return False, 0


# 修改：主函数（JSON格式输出）
def extract_commit_diffs(commit_urls, clone_directory="tmp/valid_vul_repos/", output_path = "none.json"):
# def extract_commit_diffs(commit_urls, clone_directory="tmp/valid_nonvul_repos/",output_path="valid_commit_diffs_nonvul_results.json"):
    """主函数：提取commit差异并保存为JSON"""
    processed_count = 0
    skipped_count = 0
    error_count = 0

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    os.makedirs(clone_directory, exist_ok=True)

    logger.info(f"Starting processing {len(commit_urls)} commits")

    for commit_url in commit_urls:
        try:
            parts = commit_url.split('/')
            repo_owner = parts[-4]
            repo_name = parts[-3]
            commit_sha = parts[-1]

            if is_commit_processed(output_path, repo_owner, repo_name, commit_sha):
                logger.info(f"Skipping already processed commit: {repo_owner}/{repo_name}@{commit_sha[:7]}")
                skipped_count += 1
                continue

            clone_path = os.path.join(clone_directory, repo_owner, repo_name)

            if not os.path.exists(clone_path):
                try:
                    if clone_with_retry(repo_owner, repo_name, clone_directory):
                        logger.info(f"Successfully cloned {repo_owner}/{repo_name}")
                except Exception as e:
                    logger.error(f"Failed to clone {repo_owner}/{repo_name}: {str(e)}")
                    error_count += 1
                    continue

            temp_diff = git_diff_with_retry(clone_path, commit_sha)
            if temp_diff is None:
                logger.warning(f"Skipping commit {commit_sha[:7]} due to diff error or invalid format")
                error_count += 1
                continue

            # 为每个diff添加元数据
            if isinstance(temp_diff, list):
                for item in temp_diff:
                    item.update({
                        'repo_owner': repo_owner,
                        'repo_name': repo_name,
                        'commit_sha': commit_sha,
                        'commit_url': commit_url
                    })
            elif isinstance(temp_diff, dict):
                temp_diff.update({
                    'repo_owner': repo_owner,
                    'repo_name': repo_name,
                    'commit_sha': commit_sha,
                    'commit_url': commit_url
                })
            # print(temp_diff[0])
            processed_commit = process_commit(temp_diff)

            success, current_count = append_to_json(output_path, processed_commit)
            if success:
                processed_count += 1
                logger.info(f"Processed commit {commit_sha[:7]} (Total items: {current_count})")
            else:
                error_count += 1

        except Exception as e:
            logger.error(f"Error processing commit {commit_url}: {str(e)}", exc_info=True)
            error_count += 1
            continue

    logger.info(f"\nProcessing complete. Results saved to {output_path}")
    logger.info(f"Total processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count}")





def build_input(commit_msg, git_diff):
    """基础拼接（带特殊标记符）"""
    return f"[CLS]{commit_msg}[SEP]{git_diff}[EOS]"

def check_token_count(text, max_len=512):
    """Token计数与检查"""
    tokens = tokenizer(text, truncation=False)["input_ids"]
    return len(tokens), len(tokens) > max_len

def smart_truncate_diff(git_diff, reserve_lines=20):
    """保留关键差异的智能截断"""
    lines = git_diff.split('\n')
    # 优先级：差异头 > 新增代码 > 删除代码 > 上下文
    key_lines = [
        l for l in lines
        if l.startswith('@@') or
        l.startswith('+') or
        l.startswith('-')
    ][:reserve_lines]
    # 补全最后一个差异块
    last_idx = min(reserve_lines, len(lines))
    return '\n'.join(key_lines + lines[last_idx:last_idx+3])  # 保留3行上下文

def truncate_input(commit_msg, git_diff, max_retry=3):
    """迭代式截断直到符合长度"""
    for _ in range(max_retry):
        truncated_diff = smart_truncate_diff(git_diff)
        input_text = build_input(commit_msg, truncated_diff)
        token_len, is_over = check_token_count(input_text)
        if not is_over:
            return input_text, token_len
    return None, 0  # 截断失败


def summarize_commit_message(msg):
    """安全提取commit message中的关键安全信息"""
    if not msg or not isinstance(msg, str):
        return "Security update"

    # 匹配CVE/GHSA ID
    vuln_ids = re.findall(r'(CVE-\d+-\d+|GHSA-\w+-\w+-\w+)', msg)
    id_part = ' '.join(vuln_ids) if vuln_ids else ""

    # 提取安全相关动作描述
    action_match = re.search(
        r'(fix|patch|prevent|secure|mitigate|resolve)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)*)\s+(vulnerability|issue|bug|exploit|weakness)',
        msg.lower()
    )

    if action_match:
        action_desc = ' '.join(action_match.groups())
    else:
        # 回退方案：提取第一个动词短语
        fallback_match = re.search(r'(fix|patch|prevent|secure)\s+([^\n]+)', msg.lower())
        action_desc = fallback_match.group(0) if fallback_match else "security fix"

    return f"{id_part} {action_desc}".strip()

# def summarize_commit_message(msg):
#     """提取安全关键信息"""
#     # 匹配CVE/GHSA ID
#     vuln_ids = re.findall(r'(CVE-\d+-\d+|GHSA-\w+-\w+-\w+)', msg)
#     # 提取动词+对象（如"fix XSS vulnerability"）
#     action_desc = ' '.join(re.findall(
#         r'(fix|patch|prevent|secure)\s([a-zA-Z]+)\s(vulnerability|issue)',
#         msg.lower()
#     )[0] if re.search(r'(fix|patch)', msg.lower()) else [])
#     return f"{' '.join(vuln_ids)} {action_desc}"

def process_commit(commit_data):
    """完整处理管道"""
    # 阶段1：基础检查

    if isinstance(commit_data, list):
        if not commit_data:
            return {"status": "error", "reason": "empty commit data"}
        # 取列表中的第一个元素（假设包含所需信息）
        commit_data = commit_data[0]
    if not isinstance(commit_data, dict):
        return {"status": "error", "reason": f"invalid data type: {type(commit_data)}"}

    raw_input = build_input(commit_data["message"], commit_data["raw_patch"])
    token_len, is_over = check_token_count(raw_input)

    if not is_over:
        commit_data["input"] = raw_input
        # commit_data["token_count"] = token_len
        commit_data["status"] = "original"
        return commit_data

    # 阶段3：智能截断
    truncated_input, truncated_len = truncate_input(
        commit_data["message"],
        commit_data["raw_patch"]
    )
    if truncated_input:
        commit_data["input"] = truncated_input
        # commit_data["token_count"] = truncated_len
        commit_data["status"] = "truncated"
        return commit_data


    # 阶段4：最终摘要
    short_msg = summarize_commit_message(commit_data["message"])
    final_input = build_input(short_msg, smart_truncate_diff(commit_data["raw_patch"], 10))

    commit_data["input"] = final_input
    # commit_data["token_count"] = str(len(tokenizer(final_input)["input_ids"])),
    commit_data["status"] = "summary"
    return commit_data


def process_extracted_json_file(input_path, output_path):
    """处理整个commit JSON文件"""
    # 读取输入文件
    with open(input_path, 'r', encoding='utf-8') as f:
        commits = json.load(f)

    # 处理每个commit
    for commit in commits:
        processed_data = process_commit(commit)
        commit.update(processed_data)

    # 写入输出文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(commits, f, indent=2, ensure_ascii=False)

    return len(commits)

def build_final_dataset(input_path, output_path,label):
    """处理整个commit JSON文件"""
    # 读取输入文件
    dataset = []
    with open(input_path, 'r', encoding='utf-8') as f:
        commits = json.load(f)

    # 处理每个commit
    for commit in commits:
        dict = {}
        dict["input"] = commit["input"]
        dict["label"] = label
        dataset.append(dict)


    # 写入输出文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    return len(dataset)


def read_commit_urls_from_json(json_file: str) -> List[str]:
    """
    从JSON文件中读取commit信息并拼接为完整的commit URL列表

    Args:
        json_file: 包含commit信息的JSON文件路径

    Returns:
        完整的commit URL列表，格式如：
        [
            "https://gitee.com/openharmony/kernel_linux_5.10/commit/ef47c9ae55d4447d98c6035b67d673785068dc72",
            "https://gitee.com/openharmony/kernel_linux_5.10/commit/bf2006cb0d2794b381b49bbb79f780129765d0cf",
            ...
        ]
    """
    commit_urls = []

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for commit in data:
        # for commit in data.get("commits", []):
            repo_url = commit["repo_url"]
            sha = commit["sha"]
            # sha = commit["commit_sha"]
            # 拼接完整的commit URL
            commit_url = f"{repo_url}/commit/{sha}"
            commit_urls.append(commit_url)

        print(f"从 {json_file} 成功读取 {len(commit_urls)} 个commit URL")
        return commit_urls

    except Exception as e:
        print(f"读取JSON文件 {json_file} 失败: {str(e)}")
        return []

if __name__ == "__main__":

    # 读取训练集数据
    # module 1 从文件中读取commit url，提取diff

    ## 带参数读取训练集
    # parser = argparse.ArgumentParser(description='处理PR文件信息')
    # parser.add_argument('--input', '-i', required=True, help='输入JSON文件路径')
    # parser.add_argument('--output', '-o', required=True, help='输出JSON文件路径')
    #
    # args = parser.parse_args()
    # commit_urls = read_commit_urls_from_json(args.input)
    # extract_commit_diffs(commit_urls,output_path=args.output)
    #


    #Module 3 把commit diff提取为train input
    # build_final_dataset("valid_commit_diffs_nonvul_results.json", "valid_nonvul_dataset.json",0)
    # build_final_dataset("valid_commit_diffs_vul_results.json", "valid_vul_dataset.json",1)



#------------------------------------------------------


    # 把正负数据集拼在一起并且打标签


    print("Loading datasets...")

    # 加载漏洞数据并添加标签（1表示漏洞）
    # vul_dataset = load_dataset('json', data_files="valid_commit_diffs_vul_results.json")['train']
    vul_dataset = load_dataset('json', data_files="all_nothree_vul_commit_diff.json")['train']
    vul_dataset = vul_dataset.map(lambda x: {'label': 1})  # 添加标签1

    # 加载非漏洞数据并添加标签（0表示非漏洞）
    # nonvul_dataset = load_dataset('json', data_files="valid_commit_diffs_nonvul_results.json")['train']
    nonvul_dataset = load_dataset('json', data_files="all_nothree_nonvul_commit_diff.json")['train']
    nonvul_dataset = nonvul_dataset.map(lambda x: {'label': 0})  # 添加标签0

    # 合并数据集
    full_dataset = concatenate_datasets([vul_dataset, nonvul_dataset])
    # full_dataset = vul_dataset


    # 统一重命名标签字段（可选，如果后续需要特定字段名）
    # full_dataset = full_dataset.rename_column("label", "labels")

    # 确保输出目录存在
    import os

    os.makedirs("./valid_dataset", exist_ok=True)

    # 保存数据集
    # 保存为JSON
    with open( "valid_nothree_commit_dataset.json", "w") as f:
        json.dump(full_dataset.to_list(), f, indent=2)  # 转换为列表格式保存

    print(f"数据集合并完成，总样本数：{len(full_dataset)}")
    print(f"漏洞样本数：{len(vul_dataset)}，非漏洞样本数：{len(nonvul_dataset)}")





