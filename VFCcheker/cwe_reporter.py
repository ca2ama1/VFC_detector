import json

from git import Repo
from openai import OpenAI
from pygments.lexers import CLexer
import os



def analyze_cwe(repo_path, commit_hash, analysis_patterns):

    try:
        # api_key = os.getenv("VOLC_ARK_API_KEY")
        api_key = "696cf87d-a374-4bc0-911e-7adfde31e751"
        if not api_key:
            print("警告：未在环境变量 VOLC_ARK_API_KEY 中找到API Key，将使用代码中提供的备用Key。")

        client = OpenAI(
            api_key=api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )
    except Exception as e:
        print(f"  [×] 错误：初始化OpenAI客户端失败 - {e}")
        return None

    # 获取上下文
    repo = Repo(repo_path)
    commit = repo.commit(commit_hash)

    code_changes_str = ""
    for file_path, patterns in analysis_patterns.items():
        code_changes_str += f"文件: {file_path}\n"
        code_changes_str += f"代码变更上下文 (Hunk):\n"
        for pattern in patterns:
            code_changes_str += "```diff\n"
            code_changes_str += pattern
            code_changes_str += "\n```\n\n"

    prompt = f"""
    你是一名顶级的代码安全审计专家和漏洞分析师。
    你的任务是分析以下Git commit信息和代码变更，识别其中修复的漏洞类型，并以CWE（Common Weakness Enumeration）的形式进行总结。
    
    --- Commit信息 ---
    Commit Hash: {commit.hexsha}
    Author: {commit.author.name} <{commit.author.email}>
    Date: {commit.authored_datetime}
    Commit Message:
    {commit.message}
    
    --- 代码变更详情 (Diff Hunks) ---
    {code_changes_str}
    
    --- 任务要求 ---
    请基于以上所有信息，进行深入分析，并严格按照以下JSON格式输出你的分析结果。不要在JSON前后添加任何额外的解释或说明文字。
    如果无法确定具体的CWE编号，请在 cwe_id 字段中填写 "N/A"。
    
    ```json
    {{
      "cwe_id": "例如：CWE-125",
      "cwe_description": "对一个超出边界的内存位置进行读操作。",
      "impact": "可能导致信息泄露、程序崩溃或潜在的远程代码执行。",
      "affected_repository": "仓库的名称",
      "affected_files": ["文件路径1", "文件路径2"],
      "fix_commit_link": "修复该漏洞的commit链接"
    }}

"""


    # 火山api格式
    try:
        completion = client.chat.completions.create(
            model="ep-20250510100057-d6hzw",  # 模型名称
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
        )

        response_content = completion.choices[0].message.content

        if response_content.startswith("```json"):
            response_content = response_content.strip("```json\n").strip("```")

        cwe_info = json.loads(response_content)

        # 补充和修正模型可能没有的信息
        repo_name = os.path.basename(repo.working_dir)
        cwe_info['affected_repository'] = repo_name
        cwe_info['fix_commit_link'] = f"[https://gitee.com/openharmony/kernel_liteos_a/commit/{commit.hexsha}]"

        return cwe_info

    except json.JSONDecodeError:
        print("  [×] 错误：模型返回的不是有效的JSON格式。")
        print("模型原始输出：\n", response_content)
        return None
    except Exception as e:
        print(f"  [×] 错误：调用大模型API时发生未知错误 - {e}")
        return None