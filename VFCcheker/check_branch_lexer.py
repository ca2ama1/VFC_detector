import git
from git import Repo
from unidiff import PatchSet
from pygments.lexers import CLexer
from pygments.token import Token
import os
from cwe_reporter import analyze_cwe
import pandas as pd
import sys

# 检测的分支
BRANCH_LIST = [
    "origin/master",
    "origin/OpenHarmony-4.1-Release",
    "origin/OpenHarmony-5.0.3-Release",
    "origin/OpenHarmony-5.1.0-Release"
]
# 考虑的上下文行数
CONTEXT_LINES = 4
# 选择忽视的token类型
IGNORE_TYPES = {Token.Name, Token.Text, Token.Comment}


# def analyze_commit_for_cwe(repo_path, commit_hash, analysis_patterns):
#     """
#     调用大模型API分析Commit信息和代码变更，提取CWE信息。
#
#     Args:
#         repo_path (str): 仓库的本地路径。
#         commit_hash (str): 要分析的Commit的哈希值。
#         analysis_patterns (dict): 从get_analysis_patterns获取的代码模式。
#
#     Returns:
#         dict: 包含CWE分析结果的字典，或在失败时返回None。
#     """
#     print("\n" + "=" * 60 + "\n正在调用大模型进行CWE分析...")
#
#     # 1. 初始化API客户端
#     try:
#         # 最佳实践：从环境变量读取API Key，而不是硬编码
#         # 请设置环境变量: export VOLC_ARK_API_KEY="您的API Key"
#         api_key = "696cf87d-a374-4bc0-911e-7adfde31e751"
#         if not api_key:
#             # 如果环境变量中没有，作为后备方案，使用您提供的密钥（不推荐用于生产）
#             print("警告：未在环境变量 VOLC_ARK_API_KEY 中找到API Key，将使用代码中提供的备用Key。")
#             api_key = "696cf87d-a374-4bc0-911e-7adfde31e751"  # 仅为示例，请替换或删除
#
#         client = OpenAI(
#             api_key=api_key,
#             base_url="https://ark.cn-beijing.volces.com/api/v3",
#         )
#     except Exception as e:
#         print(f"  [×] 错误：初始化OpenAI客户端失败 - {e}")
#         return None
#
#     # 2. 准备提交给模型的上下文信息
#     repo = Repo(repo_path)
#     commit = repo.commit(commit_hash)
#
#     # 将代码变更格式化为字符串
#     code_changes_str = ""
#     for file_path, patterns in analysis_patterns.items():
#         code_changes_str += f"文件: {file_path}\n"
#         code_changes_str += f"代码变更上下文 (Hunk):\n"
#         for pattern in patterns:
#             code_changes_str += "```diff\n"
#             # Hunk内容通常以 @@ 开头，我们保留它以提供更多上下文
#             code_changes_str += pattern
#             code_changes_str += "\n```\n\n"
#
#     # 3.精心构建Prompt
#     prompt = f"""
# 你是一名顶级的代码安全审计专家和漏洞分析师。
# 你的任务是分析以下Git commit信息和代码变更，识别其中修复的漏洞类型，并以CWE（Common Weakness Enumeration）的形式进行总结。
#
# --- Commit信息 ---
# Commit Hash: {commit.hexsha}
# Author: {commit.author.name} <{commit.author.email}>
# Date: {commit.authored_datetime}
# Commit Message:
# {commit.message}
#
# --- 代码变更详情 (Diff Hunks) ---
# {code_changes_str}
#
# --- 任务要求 ---
# 请基于以上所有信息，进行深入分析，并严格按照以下JSON格式输出你的分析结果。不要在JSON前后添加任何额外的解释或说明文字。
# 如果无法确定具体的CWE编号，请在 cwe_id 字段中填写 "N/A"。
#
# ```json
# {{
#   "cwe_id": "例如：CWE-125",
#   "cwe_description": "对一个超出边界的内存位置进行读操作。",
#   "impact": "可能导致信息泄露、程序崩溃或潜在的远程代码执行。",
#   "affected_repository": "仓库的名称",
#   "affected_files": ["文件路径1", "文件路径2"],
#   "fix_commit_link": "修复该漏洞的commit链接"
# }}
#
# """
#
#
#     # 4. 调用API并处理响应
#     try:
#         print("  - 正在向大模型发送请求...")
#         completion = client.chat.completions.create(
#             model="ep-20250510100057-d6hzw",  # 使用您指定的模型
#             messages=[
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.1,  # 使用较低的温度以获得更稳定、更精确的输出
#         )
#
#         response_content = completion.choices[0].message.content
#         print("  - 成功接收到模型响应。")
#
#         # 5. 解析JSON结果
#         # 模型可能在JSON代码块前后添加"```json\n"和"```"，需要先去除
#         if response_content.startswith("```json"):
#             response_content = response_content.strip("```json\n").strip("```")
#
#         cwe_info = json.loads(response_content)
#
#         # 补充和修正模型可能没有的信息
#         repo_name = os.path.basename(repo.working_dir)
#         cwe_info['affected_repository'] = repo_name
#         # 假设commit链接的格式，您可能需要根据自己的git托管平台修改
#         cwe_info[
#             'fix_commit_link'] = f"[https://gitee.com/openharmony/kernel_liteos_a/commit/{commit.hexsha}]"
#
#         return cwe_info
#
#     except json.JSONDecodeError:
#         print("  [×] 错误：模型返回的不是有效的JSON格式。")
#         print("模型原始输出：\n", response_content)
#         return None
#     except Exception as e:
#         print(f"  [×] 错误：调用大模型API时发生未知错误 - {e}")
#         return None



def get_line_number_from_token_index(tokens, index):
    if index >= len(tokens):
        return -1
    line_number = 1
    for i in range(index):
        line_number += tokens[i][1].count('\n')
    return line_number


def compare_tokens_flexibly(source_token, pattern_token, types_to_ignore_value_for):
    """
    使用基于Token的灵活匹配方法，检查指定分支是否存在漏洞代码结构。
    这个版本被修改为可以智能处理父子Token类型关系。
    """
    source_type, source_value = source_token
    pattern_type, pattern_value = pattern_token

    # if source_value=="g_processMaxNum" or pattern_value=="g_processMaxNum":
    #     print(1)


    # Token.Name特殊处理，同一个lexer有时会被parse成不同类型的token.name
    if source_type != pattern_type:
        if {source_type, pattern_type}.issubset(
                {Token.Name, Token.Name.Builtin, Token.Keyword.Type, Token.Name.Function}):
            pass
        else:
            return False

    # 忽略IGNORE_TYPES及其所有子类型
    current_type = source_type
    while current_type is not None:
        if current_type in types_to_ignore_value_for:
            return True
        # 继续向上查找父类型
        current_type = current_type.parent

    return source_value == pattern_value

def compare_tokens_hard(source_token, pattern_token, types_to_ignore_value_for):
    """
    严格匹配，除了token类型之外也匹配token的具体值
    """
    source_type, source_value = source_token
    pattern_type, pattern_value = pattern_token

    return source_value == pattern_value


def find_flexible_matches(source_tokens_original, effective_pattern, types_to_ignore_value_for):
    """
    滑动窗口在在源Token序列中寻找与模式Token序列匹配的片段
    返回一个包含 (起始索引, 结束索引) 的列表
    """
    if not effective_pattern:
        return []
    n_source = len(source_tokens_original)
    n_pattern = len(effective_pattern)
    found_match_spans = []
    source_cursor = 0
    while source_cursor < n_source:
        while source_cursor < n_source and source_tokens_original[source_cursor][0] == Token.Text.Whitespace:
            source_cursor += 1
        if source_cursor >= n_source:
            break
        pattern_idx = 0
        temp_source_idx = source_cursor
        first_matched_token_original_index = -1
        last_matched_token_original_index = -1
        while pattern_idx < n_pattern and temp_source_idx < n_source:
            current_source_token = source_tokens_original[temp_source_idx]
            if current_source_token[0] == Token.Text.Whitespace:
                temp_source_idx += 1
                continue
            current_pattern_token = effective_pattern[pattern_idx]
            # to be changed
            if compare_tokens_flexibly(current_source_token, current_pattern_token, types_to_ignore_value_for) or compare_tokens_flexibly(current_source_token, current_pattern_token, {}):
                if first_matched_token_original_index == -1:
                    first_matched_token_original_index = temp_source_idx
                last_matched_token_original_index = temp_source_idx
                pattern_idx += 1
                temp_source_idx += 1
            else:
                break
        if pattern_idx == n_pattern:
            if first_matched_token_original_index != -1:
                found_match_spans.append((first_matched_token_original_index, last_matched_token_original_index))
        source_cursor += 1
    return list(set(found_match_spans))


def get_analysis_patterns(repo_path, commit_hash, context_lines):
    """
    解析Commit，智能提取漏洞模式。
    新逻辑：无论修复是增加还是删除，都统一提取 "修复前" 的代码状态
    （即上下文 + 被删除的代码）作为漏洞模式。
    """
    repo = Repo(repo_path)
    try:
        commit = repo.commit(commit_hash)
        print(f"成功获取Commit: {commit.hexsha}")
    except git.exc.BadName as e:
        print(f"错误：找不到Commit {commit_hash} - {e}")
        return None
    if not commit.parents:
        print("错误：该Commit没有父节点（可能是初始提交）")
        return None

    parent = commit.parents[0]
    # 获取diff，-U参数确保我们有足够的上下文
    diff_text = repo.git.diff(parent.hexsha, commit.hexsha, f'-U{context_lines}')
    patch_set = PatchSet(diff_text)

    analysis_patterns = {}
    print(f"发现 {len(patch_set)} 个文件差异...")
    for patched_file in patch_set:
        # 跳过纯粹的新增或删除文件
        if patched_file.is_removed_file or patched_file.is_added_file:
            continue

        file_path = patched_file.source_file
        if file_path.startswith('a/'):
            file_path = file_path[2:]

        file_patterns = []
        for hunk in patched_file:
            # --- 这是新的、统一的核心逻辑 ---
            # 我们要构建的是 "修复前" 的代码快照。
            # 它由上下文（context）和被删除（removed）的行组成。

            pre_fix_lines = []
            for line in hunk:
                # 只要不是新增的行（以'+'开头），就都属于 "修复前" 的状态
                if not line.is_added:
                    pre_fix_lines.append(line.value)

            # 如果这个hunk里确实提取出了有效的代码行，就将它作为一个模式
            if pre_fix_lines:
                pattern_string = "".join(pre_fix_lines)
                # 确保我们提取的模式不只是空白符
                if pattern_string.strip():
                    file_patterns.append(pattern_string)

        if file_patterns:
            print(f"在文件 {file_path} 中找到 {len(file_patterns)} 个待分析的模式。")
            analysis_patterns[file_path] = file_patterns

    return analysis_patterns


def check_branch_flexible(repo, branch, analysis_patterns):
    """
    使用基于Token的灵活匹配方法，检查指定分支是否存在漏洞代码结构。
    """
    try:
        print(f"  正在切换到分支: {branch}...")
        repo.git.checkout(branch, force=True)
        print(f"  切换成功。")
    except git.exc.GitCommandError as e:
        return {'error': f"分支切换失败：{str(e)}"}

    results = {}
    lexer = CLexer()
    # IGNORE_TYPES
    types_to_ignore_value_for = IGNORE_TYPES

    for file_path, patterns in analysis_patterns.items():
        full_path = os.path.join(repo.working_dir, file_path)
        file_status = {}

        if not os.path.exists(full_path):
            file_status['status'] = 'file_not_found'
        else:
            try:
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    source_code = f.read()

                source_tokens = list(lexer.get_tokens(source_code))
                all_matches_info = []

                for i, target_pattern in enumerate(patterns):
                    if not target_pattern.strip(): continue
                    target_tokens = list(lexer.get_tokens(target_pattern))
                    effective_pattern = [
                        token for token in target_tokens if token[0] != Token.Text.Whitespace
                    ]
                    if not effective_pattern: continue
                    matching_spans = find_flexible_matches(source_tokens, effective_pattern, types_to_ignore_value_for)

                    if matching_spans:
                        print(f"    - 在 {file_path} 中找到模式 #{i + 1} 的 {len(matching_spans)} 个匹配。")
                        for start_idx, end_idx in matching_spans:
                            start_line = get_line_number_from_token_index(source_tokens, start_idx)
                            matched_tokens = source_tokens[start_idx: end_idx + 1]
                            matched_code = "".join([val for tp, val in matched_tokens])
                            all_matches_info.append({
                                'line': start_line,
                                'code': matched_code.strip()
                            })

                if all_matches_info:
                    file_status['status'] = 'vulnerable'
                    file_status['matches'] = all_matches_info
                else:
                    file_status['status'] = 'safe'
            except Exception as e:
                file_status['error'] = f"文件处理失败：{str(e)}"
        results[file_path] = file_status
    return results


def execute(repo_path, commit_hash):
    if not os.path.isdir(repo_path):
        print(f"错误：仓库路径不存在 '{repo_path}'")
        return

    repo = Repo(repo_path)
    original_state = None
    try:
        original_state = repo.active_branch
        print(f"当前活动分支为: {original_state.name}，将在扫描后恢复。")
    except TypeError:
        original_state = repo.head.commit
        print(f"警告：仓库处于 detached HEAD 状态，指向 {original_state.hexsha[:10]}。将在扫描后恢复。")

    try:
        initial_branch_name = BRANCH_LIST[0].split('/')[-1] if '/' in BRANCH_LIST[0] else BRANCH_LIST[0]
        repo.git.checkout(initial_branch_name)
    except Exception as e:
        print(f"警告：无法切换到初始分支 {BRANCH_LIST[0]}。错误：{e}")

    # 找到漏洞代码快
    analysis_patterns = get_analysis_patterns(repo_path, commit_hash, context_lines=CONTEXT_LINES)

    if not analysis_patterns:
        print("分析完成：未在修复Commit中发现可分析的漏洞模式。")
        return
    # 开启cwe分析
    # cwe_results = analyze_cwe(repo_path, commit_hash, analysis_patterns)
    cwe_results = 0

    # 打印CWE分析报告
    if cwe_results:
        print("\n" + "=" * 60 + "\nCWE 漏洞分析报告:")
        print(f"  CWE 编号: {cwe_results.get('cwe_id', 'N/A')}")
        print(f"  CWE 描述: {cwe_results.get('cwe_description', 'N/A')}")
        print(f"  潜在影响: {cwe_results.get('impact', 'N/A')}")
        print(f"  受影响仓库: {cwe_results.get('affected_repository', 'N/A')}")
        print(f"  受影响文件: {cwe_results.get('affected_files', [])}")
        print(f"  修复Commit: {cwe_results.get('fix_commit_link', 'N/A')}")
        print("\n" + "=" * 60 + "\n")
    else:
        print("\n" + "=" * 60 + "\nCWE 漏洞分析失败。")


    print(f"\n分析到 {len(analysis_patterns)} 个文件存在待分析的模式。开始跨分支扫描...")
    all_remote_branches = [ref.name for ref in repo.references if isinstance(ref, git.RemoteReference)]
    results = {}

    # 检测其他分支
    for branch in all_remote_branches:
        if branch not in BRANCH_LIST:
            continue
        print(f"\n>>>>>> 正在检查分支: {branch} <<<<<<")
        try:
            branch_results = check_branch_flexible(repo, branch, analysis_patterns)
            results[branch] = branch_results
        except Exception as e:
            results[branch] = {'error': str(e)}

    print(f"\n扫描完成，正在恢复到原始状态...")
    if original_state:
        try:
            repo.git.checkout(original_state)
            print("已成功恢复仓库状态。")
        except Exception as e:
            print(f"错误：无法恢复到原始状态 ({original_state})。错误: {e}")

    print("\n" + "=" * 60 + "\n漏洞存在性检测报告：")
    for branch, data in results.items():
        print(f"\n--- 分支：{branch} ---")
        if 'error' in data:
            print(f"  [×] 扫描错误：{data['error']}")
            continue
        vulnerable_files_count = 0
        for file, status in data.items():
            if status.get('status') == 'vulnerable' and status.get('matches'):
                vulnerable_files_count += 1
                print(f"  [×] 发现漏洞文件：{file}")
                match_info = status['matches'][0]
                line_num = match_info['line']
                snippet = match_info['code']
                print(f"    匹配位置：从第 {line_num} 行开始")
                print("    匹配到的代码片段示例:")
                print("    " + "-" * 40)
                for line in snippet.splitlines():
                    print(f"    | {line}")
                print("    " + "-" * 40)
            elif status.get('status') == 'file_not_found':
                print(f"  [!] 文件在该分支中不存在：{file}")
            elif status.get('error'):
                print(f"  [!] 文件处理错误：{file} - {status['error']}")
        if vulnerable_files_count == 0 and 'error' not in data:
            print("  [√] 未发现漏洞模式，此分支相对安全。")


def batch_processor(repo_directory, csv_path):
    """
    从CSV文件批量读取commit SHA

    """

    try:
        df = pd.read_csv(csv_path)
        if 'sha' not in df.columns:
            print(f"错误：CSV文件 '{csv_path}' 中必须包含一个名为 'sha' 的列。")
            return
    except FileNotFoundError:
        print(f"错误：找不到CSV文件 '{csv_path}'。")
        return
    except Exception as e:
        print(f"读取CSV文件时发生错误: {e}")
        return

    original_stdout = sys.stdout  # 保存原始的标准输出（控制台）
    commit_hashes = df['sha'].tolist()

    print(f"发现 {len(commit_hashes)} 个 commit-hash，开始批量处理...")

    for commit_hash in commit_hashes[0:10]:
        commit_hash = str(commit_hash).strip()
        report_filename = f"analysis_report_{commit_hash}.txt"

        # 在控制台打印当前进度
        print(f"\n正在处理: {commit_hash} -> 结果将保存至: {report_filename}")

        try:
            # 3. 将输出重定向到文件
            with open(report_filename, 'w', encoding='utf-8') as report_file:
                sys.stdout = report_file

                # 调用你已有的核心分析函数
                execute(repo_directory, commit_hash)

        except Exception as e:
            # 如果执行过程中出现异常，也要恢复输出并打印错误
            sys.stdout = original_stdout
            print(f"处理 {commit_hash} 时发生严重错误: {e}")
        finally:
            # 4. 恢复标准输出到控制台
            sys.stdout = original_stdout

    print("\n所有任务处理完毕。")


if __name__ == '__main__':

    repo_directory = "./kernel_liteos_a"
    csv_file_path = "file/commit_vfc_newmodel_823.csv"
    batch_processor(repo_directory, csv_file_path)

    # # 一个主要靠删除代码修复的Commit
    # # fix_commit_hash = "94ac2627be20cfd161285c80e3d491127e242da6"
    # # 一个主要靠增加代码修复的Commit
    # fix_commit_hash = "0d1635757f19cb29ac6526cbcf5491fec5b103f8"
    # # g_processMaxNum
    # # fix_commit_hash = "b273ddc98dae8dbac7b399d55af04e4b6351244d"
    # execute(repo_directory, fix_commit_hash)







