import git
from git import Repo
from unidiff import PatchSet
import os
import sys


branch_list=[
    "origin/master",
    "origin/OpenHarmony-4.0-Release",
    "origin/OpenHarmony-5.0.3-Release",
    "origin/OpenHarmony-5.1.0-Release"
]

def get_vulnerable_lines(repo_path, commit_hash):
    """
    解析修复Commit的差异，提取被删除的代码行。
    """
    repo = Repo(repo_path)
    try:
        commit = repo.commit(commit_hash)
        print(f"成功获取Commit: {commit.hexsha}")
    except ValueError:
        print(f"错误：找不到Commit {commit_hash}")
        return None

    if not commit.parents:
        print("错误：该Commit没有父节点（可能是初始提交）")
        return None

    parent = commit.parents[0]
    # create_patch=True 是为了生成我们可以解析的文本diff
    diffs = parent.diff(commit, create_patch=True)
    vulnerable_lines = {}

    print(f"发现 {len(diffs)} 个文件差异...")
    for diff_entry in diffs:
        # 我们只关心被修改(M)或被删除(D)的文件，且这些文件在之前是存在的(a_path)
        # if diff_entry.change_type not in ('M', 'D') or not diff_entry.a_path:
        #     continue

        # diff_entry.diff 是 bytes 类型，需要解码
        # 并且要处理 diff 内容可能为空的情况 (e.g., a file that was only renamed)
        if not diff_entry.diff:
            continue

        diff_text = diff_entry.diff.decode('utf-8', errors='replace')

        old_path = diff_entry.a_path
        deleted_lines = []

        # 按行分割diff文本
        for line in diff_text.splitlines():
            # 被删除的行以'-'开头，但我们要排除文件头'---'
            if line.startswith('-') and not line.startswith('---'):
                # 移除行首的'-'和两边的空白符
                cleaned_line = line[1:].strip()
                deleted_lines.append(cleaned_line)

        if deleted_lines:
            print(f"在文件 {old_path} 中找到被删除的行。")
            vulnerable_lines[old_path] = deleted_lines

    return vulnerable_lines

def check_branch_brute(repo, branch, vulnerable_lines):
    """最笨的一种方法，强行查找相同代码所在行"""
    try:
        repo.git.checkout(branch)
    except git.exc.GitCommandError as e:
        return {'error': f"分支切换失败：{str(e)}"}

    results = {}
    for file_path, lines in vulnerable_lines.items():
        full_path = os.path.join(repo.working_dir, file_path)
        file_status = {}
        found=[]
        if not os.path.exists(full_path):
            file_status['status'] = 'file_not_found'
        else:
            try:
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = [line.rstrip('\n') for line in f.readlines()]
                    content_full= f.readlines()
                # print(content_full)
                # print(content)
                for line in lines:
                    for content_line in content:
                        if line in content_line:
                            found.append(line)
                # found = [line for line in lines if line in content]
                file_status['status'] = 'vulnerable' if found else 'safe'
                file_status['lines_found'] = found
            except Exception as e:
                file_status['error'] = f"文件读取失败：{str(e)}"
        
        results[file_path] = file_status
    return results



def main(repo_path, commit_hash):

    repo = Repo(repo_path)


    try:
        # This works if HEAD is on a branch
        original_state = repo.active_branch
        print(f"当前活动分支为: {original_state.name}，将在扫描后恢复。")
    except TypeError:
        # This handles the "detached HEAD" state
        original_state = repo.head.commit
        print(f"警告：仓库处于 detached HEAD 状态，指向 {original_state.hexsha[:10]}。将在扫描后恢复。")
    vulnerable_lines = get_vulnerable_lines(repo_path, commit_hash)
    if not vulnerable_lines:
        print("未发现漏洞代码变更")
        return

    print(f"分析到{len(vulnerable_lines)}个文件存在变更")

    # 获取所有远程分支
    branches = [ref.name for ref in repo.references if isinstance(ref, git.RemoteReference)]
    results = {}

    for branch in branches:
        if branch not in branch_list:
            continue
        print(f"\n正在检查分支: {branch}")
        try:
            branch_results = check_branch_brute(repo, branch, vulnerable_lines)
            results[branch] = branch_results
        except Exception as e:
            results[branch] = {'error': str(e)}
    
    # 打印结果报告
    print("\n" + "="*50 + "\n漏洞检测结果：")
    for branch, data in results.items():
        print(f"\n分支：{branch}")
        if 'error' in data:
            print(f"  × 错误：{data['error']}")
            continue
        
        vulnerable_files = 0
        for file, status in data.items():
            if status.get('status') == 'vulnerable':
                print(f"  × 漏洞文件：{file}")
                print(f"    匹配代码：{status['lines_found'][:3]}...")  # 显示前3行匹配代码
                vulnerable_files += 1
            elif status.get('status') == 'file_not_found':
                print(f"  ! 文件丢失：{file}")
            elif status.get('error'):
                print(f"  ! 错误：{file} - {status['error']}")
        
        if vulnerable_files == 0:
            print("  √ 未发现漏洞")


# main("./kernel_liteos_a", "94ac2627be20cfd161285c80e3d491127e242da6")
main("./kernel_liteos_a", "78db02de2cd1228b2875f76e1a9ad98abd5fb6f4")

# if __name__ == "__main__":
#     if len(sys.argv) != 3:
#         print("使用方法：python vulnerability_check.py <仓库路径> <修复Commit哈希>")
#         sys.exit(1)
    


    # main(sys.argv[1], sys.argv[2])
