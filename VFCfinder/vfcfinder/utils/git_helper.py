"""
Helper functions for locally cloned Git repos
"""
import datetime
import time

from datetime import datetime, timedelta  # 确保正确导入
import json
import subprocess
from threading import Timer
import os


import git
import pandas as pd
import patchparser
import requests
from packaging.version import Version


def get_gitee_repos(org_name, access_token=None, cache_file='gitee_repos_cache.json'):
    """
    获取Gitee组织下的所有仓库，带本地缓存功能（每天更新一次）

    :param org_name: 组织名称，如'openharmony'
    :param access_token: 可选，Gitee API访问令牌
    :param cache_file: 缓存文件路径
    :return: 仓库URL列表
    """
    # 检查缓存文件是否存在且是今天更新的
    if os.path.exists(cache_file):
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
        if file_time.date() == datetime.now().date():
            print("使用今天已更新的缓存文件")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

    print("从Gitee API获取最新仓库数据...")
    parent_repos = []
    page = 1
    per_page = 100  # 每页最大数量

    while True:
        # 构造API URL
        url = f"https://gitee.com/api/v5/orgs/{org_name}/repos?page={page}&per_page={per_page}&type=public"

        # 添加访问令牌（如果有）
        headers = {}
        if access_token:
            headers['Authorization'] = f'token {access_token}'

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # 检查请求是否成功
            data = response.json()

            if not data:  # 没有更多数据
                break

            # 筛选属于该组织的仓库
            for repo in data:
                namespace = repo.get('namespace', {})
                if namespace.get('path') == org_name:
                    parent_repos.append(repo)

            print(f"已获取第 {page} 页，当前仓库数: {len(parent_repos)}")

            # 检查是否还有下一页
            if len(data) < per_page:
                break

            page += 1
            # 添加延迟避免触发API限制
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            break

    # 保存到缓存文件
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(parent_repos, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到 {cache_file}")

    return parent_repos

# def get_gitee_repos(org_name, access_token=None):
#     """
#     获取Gitee组织下的所有仓库
#     :param org_name: 组织名称，如'openharmony'
#     :param access_token: 可选，Gitee API访问令牌
#     :return: 仓库URL列表
#     """
#     # repos = []
#     active_repos = []
#     parent_repos = []
#     page = 1
#     per_page = 100  # 每页最大数量
#     # print(json.dumps(response.json()[0], indent=2, ensure_ascii=False))
#
#     while True:
#         # 构造API URL
#         url = f"https://gitee.com/api/v5/orgs/{org_name}/repos?page={page}&per_page={per_page}&type=public"
#
#         # 添加访问令牌（如果有）
#         headers = {}
#         if access_token:
#             headers['Authorization'] = f'token {access_token}'
#
#         try:
#             response = requests.get(url, headers = headers)
#             response.raise_for_status()  # 检查请求是否成功
#             data = response.json()
#
#             if not data:  # 没有更多数据
#                 break
#
#             # 提取仓库URL
#             active_repos.extend([repo['html_url'] for repo in data])
#
#             for repo in data:
#                 namespace = repo.get('namespace', {})
#                 print("namespace.get('path'):",namespace.get('path'))
#                 # print("namespace.get('type'):",namespace.get('type'))
#                 if namespace.get('path') == org_name:
#                     parent_repos.append(repo)
#
#             print(f"已获取第 {page} 页，筛选后活跃仓库数: {len(parent_repos)}")
#             # 检查是否还有下一页
#             if len(data) < per_page:
#                 break
#
#             page += 1
#
#         except requests.exceptions.RequestException as e:
#             print(f"请求失败: {e}")
#             break
#
#     return parent_repos

def clone_repo(repo_type:str,repo_owner:str, repo_name:str, clone_path:str, local_name=False):
    """Clone a Git repository to a local path

    Args:
        repo_type (str): Repo Type
        repo_owner (str): Repo Owner
        repo_name (str): Repo Name
        clone_path (str): Desired clone path
        local_name (bool): If a unique clone path is set
    """
    # set path
    if not local_name:
        clone_path = f"{clone_path}{repo_owner}/"
    else:
        clone_path = f"{clone_path}"

    if not os.path.exists(clone_path):
        os.makedirs(clone_path)

    if not local_name:
        # check if clone already exists
        if os.path.exists(f"{clone_path}{repo_name}"):
            print(f"Path already exists: {clone_path}{repo_name}")
        else:
            # clone repo
            # git.Git(clone_path).clone(f"https://{GITHUB_USERNAME}:
            # {GITHUB_TOKEN}@github.com/{repo_owner}/"
            #                           f"{repo_name.replace('.git', '')}.git")
            print(f"Cloning repo to: {clone_path}{repo_name}")
            if '.com' in repo_type:
                git.Git(clone_path).clone(
                    f"https://{repo_type}/{repo_owner}/"
                    f"{repo_name.replace('.git', '')}.git"
                )
            else:
                git.Git(clone_path).clone(
                    f"https://{repo_type}.com/{repo_owner}/"
                    f"{repo_name.replace('.git', '')}.git"
                )
            # git.Git(clone_path).clone(
            #     f"https://{repo_type}/{repo_owner}/"
            #     f"{repo_name.replace('.git', '')}.git"
            # )

    else:  # specific local folder name
        # check if clone already exists
        if os.path.exists(f"{clone_path}{local_name}"):
            print(f"Path already exists: {clone_path}{local_name}")
        else:
            # clone repo
            # git.Git(clone_path).clone(
            #     f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{repo_owner}/"
            #     f"{repo_name.replace('.git', '')}.git"
            # )
            print(f"Cloning repo to: {clone_path}{local_name}")
            git.Git(clone_path).clone(
                f"https://github.com/{repo_owner}/"
                f"{repo_name.replace('.git', '')}.git"
            )

#
# def clone_repo_with_token(repo_type:str,repo_owner:str, repo_name:str, clone_path:str,token:str, local_name=False):
#     """Clone a Git repository to a local path
#
#     Args:
#         repo_type (str): Repo Type
#         repo_owner (str): Repo Owner
#         repo_name (str): Repo Name
#         clone_path (str): Desired clone path
#         local_name (bool): If a unique clone path is set
#     """
#     # set path
#     if not local_name:
#         clone_path = f"{clone_path}{repo_owner}/"
#     else:
#         clone_path = f"{clone_path}"
#
#     if not os.path.exists(clone_path):
#         os.makedirs(clone_path)
#
#         # 检查仓库是否存在
#     if not check_repo_exists(repo_type, repo_owner, repo_name, token):
#         print(f"❌ 仓库不存在或无权访问: {repo_owner}/{repo_name}")
#         return False
#
#     if not local_name:
#         # check if clone already exists
#         if os.path.exists(f"{clone_path}{repo_name}"):
#             print(f"Path already exists: {clone_path}{repo_name}")
#         else:
#             # clone repo
#             # git.Git(clone_path).clone(f"https://{GITHUB_USERNAME}:
#             # {GITHUB_TOKEN}@github.com/{repo_owner}/"
#             #                           f"{repo_name.replace('.git', '')}.git")
#             print(f"Cloning repo to: {clone_path}{repo_name}")
#             if '.com' in repo_type:
#                 git.Git(clone_path).clone(
#                     f"https://oauth2:{token}@{repo_type}/{repo_owner}/"
#                     f"{repo_name.replace('.git', '')}.git"
#                 )
#             else:
#                 git.Git(clone_path).clone(
#                     f"https://oauth2:{token}@{repo_type}.com/{repo_owner}/"
#                     f"{repo_name.replace('.git', '')}.git"
#                 )
#             # git.Git(clone_path).clone(
#             #     f"https://{repo_type}/{repo_owner}/"
#             #     f"{repo_name.replace('.git', '')}.git"
#             # )
#
#     else:  # specific local folder name
#         # check if clone already exists
#         if os.path.exists(f"{clone_path}{local_name}"):
#             print(f"Path already exists: {clone_path}{local_name}")
#         else:
#             # clone repo
#             # git.Git(clone_path).clone(
#             #     f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{repo_owner}/"
#             #     f"{repo_name.replace('.git', '')}.git"
#             # )
#             print(f"Cloning repo to: {clone_path}{local_name}")
#             git.Git(clone_path).clone(
#                 f"https://github.com/{repo_owner}/"
#                 f"{repo_name.replace('.git', '')}.git"
#             )
#
#     return True


def clone_repo_with_timeout(repo_url, clone_path, timeout=300, local_name=None):
    """
    带超时机制的git clone函数
    :param repo_url: 仓库URL
    :param clone_path: 克隆路径
    :param timeout: 超时时间(秒)，默认5分钟
    :param local_name: 自定义本地目录名
    :return: True if clone成功, False if 超时或失败
    """

    def kill_process(p):
        p.kill()

    try:
        target_path = os.path.join(clone_path, local_name) if local_name else None
        cmd = ["git", "clone", repo_url]
        if target_path:
            cmd.append(target_path)

        print(f"Executing: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, cwd=clone_path)

        timer = Timer(timeout, kill_process, [proc])
        timer.start()

        proc.communicate()  # 等待进程完成
        timer.cancel()

        if proc.returncode == 0:
            print("✅ Clone成功")
            return True
        else:
            print(f"❌ Clone失败，返回码: {proc.returncode}")
            return False
    except Exception as e:
        print(f"❌ Clone过程中发生异常: {str(e)}")
        return False


def clone_repo_with_token(repo_type: str, repo_owner: str, repo_name: str,
                          clone_path: str, token: str, local_name=False, timeout=300):
    """Clone a Git repository to a local path with timeout mechanism

    Args:
        repo_type (str): Repo Type (e.g. 'github.com')
        repo_owner (str): Repo Owner
        repo_name (str): Repo Name
        clone_path (str): Desired clone path
        token (str): Authentication token
        local_name (bool or str): If False, use repo_name; if str, use as custom dir name
        timeout (int): Timeout in seconds (default: 300)
    Returns:
        bool: True if clone succeeded, False otherwise
    """
    # set path
    if not local_name:
        clone_path = os.path.join(clone_path, repo_owner)
    else:
        clone_path = clone_path  # Use as-is for custom local_name

    # Create directory if not exists
    os.makedirs(clone_path, exist_ok=True)

    # 检查仓库是否存在
    # f not check_repo_exists(repo_type, repo_owner, repo_name, token):
    # print(f"❌ 仓库不存在或无权访问: {repo_owner}/{repo_name}")
    # return False
    # i
    # 构建仓库URL
    if '.com' in repo_type:
        repo_url = f"https://oauth2:{token}@{repo_type}/{repo_owner}/{repo_name.replace('.git', '')}.git"
    else:
        repo_url = f"https://oauth2:{token}@{repo_type}.com/{repo_owner}/{repo_name.replace('.git', '')}.git"

    # 检查是否已存在
    target_dir = local_name if isinstance(local_name, str) else repo_name
    if os.path.exists(os.path.join(clone_path, target_dir)):
        print(f"⚠️ 路径已存在: {os.path.join(clone_path, target_dir)}")
        return True

    print(f"⬇️ 正在克隆仓库到: {os.path.join(clone_path, target_dir)}")

    # 使用带超时的clone函数
    success = clone_repo_with_timeout(
        repo_url=repo_url,
        clone_path=clone_path,
        timeout=timeout,
        local_name=target_dir if isinstance(local_name, str) else None
    )

    if not success:
        print(f"❌ 克隆仓库超时或失败: {repo_owner}/{repo_name}")
        # 清理可能不完整的克隆目录
        target_path = os.path.join(clone_path, target_dir)
        if os.path.exists(target_path):
            try:
                shutil.rmtree(target_path)
                print(f"🧹 已清理不完整的克隆目录: {target_path}")
            except Exception as e:
                print(f"⚠️ 清理目录失败: {str(e)}")

    return success

def check_repo_exists(repo_type: str, repo_owner: str, repo_name: str, token: str) -> bool:
    """检查仓库是否存在且可访问"""
    url = f"https://gitee.com/api/v5/repos/{repo_owner}/{repo_name}"
    headers = {"Authorization": f"token {token}"} if token else {}

    try:
        response = requests.get(url, headers=headers)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def semver_sort(temp_versions):
    """Sorts semver tags based on pythons packaging.version

    Args:
        temp_versions (list): List of tags

    Returns:
        pd.DataFrame: Sorted tags based on semver
    """
    if temp_versions is not None:
        if len(temp_versions) > 0:
            clean_parse = []
            for each in temp_versions:
                try:
                    temp_version = Version(each)
                    temp_version.raw_version = each
                    temp_version.error = False
                    clean_parse.append(temp_version)
                except Exception as err:
                    print(err)
                    # TODO: this needs to be handled better
                    try:
                        clean_each = ".".join(each.split(".")[:3])
                        temp_version = Version(clean_each)
                        temp_version.raw_version = each
                        temp_version.error = True
                        clean_parse.append(temp_version)
                    except Exception as last_err:
                        print(f"Unkown version type, skipping: {each}")

            # sort the clean versions
            clean_parse.sort()

            clean_return = []

            for clean in clean_parse:
                clean_return.append(clean.raw_version)

            # create a df to sort the versions
            clean_return_df = pd.DataFrame(clean_return, columns=["tag"])
            clean_return_df["tag_order"] = clean_return_df.index

            return clean_return_df
    else:
        return []


def get_tags(repo_owner, repo_name, clone_path):
    """Obtains the local git repo tags for a given repository in a certain path

    Args:
        repo_owner (str): Repo owner
        repo_name (str): Name of repo
        clone_path (str): Local clone path of repo

    Returns:
        pd.DataFrame: A sorted pandas df of tags
    """

    # create repo path
    repo_path = f"{clone_path}{repo_owner}/{repo_name}/"

    # execute the git tags command
    git_tags_command = (
        f"(cd {repo_path} && "
        f"git for-each-ref --sort=v:refname --format '%(refname) %(creatordate)' refs/tags)"
    )

    # this is all trusted input....not a vulnerability
    git_tags = subprocess.check_output(
        git_tags_command, shell=True, encoding="UTF-8"
    ).splitlines()

    # load in the tag outputs
    if len(git_tags) > 0:
        temp_df = pd.DataFrame(git_tags, columns=["raw_out"])
        temp_df["repo_owner"] = repo_owner
        temp_df["repo_name"] = repo_name
        temp_df["tag_count"] = len(temp_df)

        # extract the creatordate
        temp_df["creatordate"] = temp_df.apply(
            lambda x: datetime.datetime.strptime(
                " ".join(x["raw_out"].strip("\n").split(" ")[1:-1]),
                "%a %b %d %H:%M:%S %Y",
            ),
            axis=1,
        )
        # extract the tag from the list
        temp_df["tag"] = temp_df.apply(
            lambda x: x["raw_out"].strip("\n").split(" ")[0].replace("refs/tags/", ""),
            axis=1,
        )

        # get the correct semver tag order
        temp_tags = temp_df["tag"].values.tolist()

        # sort the tags
        sorted_tags = semver_sort(temp_tags)

        # add the sorted tags back to the original df
        temp_df_sorted = pd.merge(temp_df, sorted_tags, on="tag", how="left")

    else:
        temp_df_sorted = pd.DataFrame(
            [["NO_TAGS", repo_owner, repo_name]],
            columns=["raw_out", "repo_owner", "repo_name"],
        )
        temp_df_sorted["tag_count"] = None
        temp_df_sorted["creatordate"] = None
        temp_df_sorted["tag"] = None
        temp_df_sorted["tag_order"] = None

    return temp_df


def get_all_commits(temp_repo_path: str) -> pd.DataFrame:
    """
    获取仓库所有提交（不限定标签范围）

    参数:
        temp_repo_path: 仓库路径
        limit: 最多获取的提交数量（可选）

    返回:
        pd.DataFrame 包含以下列:
        - sha: 提交哈希
        - author: 作者名
        - email: 作者邮箱
        - date: 提交日期(ISO格式)
        - message: 简短提交消息
        - full_message: 完整提交消息
    """
    repo = git.Repo(temp_repo_path)
    commits = []

    for i, commit in enumerate(repo.iter_commits('--all')):
        commits.append({
            "sha": commit.hexsha,
            "author": commit.author.name,
            "email": commit.author.email,
            "date": commit.authored_datetime.isoformat(),
            "message": commit.message.split('\n')[0].strip(),  # 第一行作为简短消息
            "full_message": commit.message.strip()
        })

    return pd.DataFrame(commits)



def get_recent_commits(temp_repo_path: str, days: int = 5) -> pd.DataFrame:
    """
    获取最近 N 天内的所有提交（默认最近 1 天）

    参数:
        temp_repo_path: 仓库路径
        days: 天数（默认 1）

    返回:
        pd.DataFrame 包含以下列:
        - sha: 提交哈希
        - author: 作者名
        - email: 作者邮箱
        - date: 提交日期(ISO格式)
        - message: 简短提交消息
        - full_message: 完整提交消息
    """
    repo = git.Repo(temp_repo_path)
    commits = []

    # 修复：使用 datetime.datetime.now() 或直接导入 datetime 类
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    print(f"仓库路径: {temp_repo_path}")
    print(f"仓库是否有效: {not repo.bare}")

    # print(f"最近 {100} 天的提交数量: {len(list(repo.iter_commits('--all', since=2025-5-11)))}")
    print(f"最近 {days} 天的提交数量: {len(list(repo.iter_commits('--all', since=since_date)))}")

    # 使用 `--since` 参数过滤最近days内的提交
    for commit in repo.iter_commits('--all', since=since_date):
        commits.append({
            "sha": commit.hexsha,
            "author": commit.author.name,
            "email": commit.author.email,
            "date": commit.authored_datetime.isoformat(),
            "message": commit.message.split('\n')[0].strip(),  # 第一行作为简短消息
            "full_message": commit.message.strip()
        })

    # if len(commits) > 0:
    #     return pd.DataFrame(commits)
    # else:
    return pd.DataFrame(commits)

def get_prior_tag(
    repo_owner: str, repo_name: str, clone_path: str, target_tag: str
) -> dict:
    """Gets the prior tag to a fixed tag and matches the
    tag to the local git tags

    Args:
        repo_owner (str): Repo owner
        repo_name (str): Name of repo
        clone_path (str): Local clone path of repo
        target_tag (str): Known vulnerable tag

    Returns:
        {prior_tag: Prior tag that matches git version
        fixed_tag: Fixed tag that matches git version}
    """

    temp_tags = get_tags(repo_owner, repo_name, clone_path)

    # get the matching tag
    tag_match = temp_tags[temp_tags["tag"].str.contains(target_tag)].tag

    # get the tag rank based on the index
    tag_match_rank = tag_match.index[0]

    # get the prior tag, based on the index
    prior_tag_rank = tag_match_rank - 1

    # prior tag
    prior_tag = temp_tags.iloc[prior_tag_rank].tag

    # return the git tag_match
    return {"prior_tag": prior_tag, "current_tag": tag_match.iloc[0]}


def get_commits_between_tags(
    prior_tag: str, current_tag: str, temp_repo_path: str
) -> pd.DataFrame:
    """Returns the commits between two tags (prior_tag...current_tag)
    Columns:
        raw_git_log,
        sha,
        message

    Args:
        prior_tag (str): prior tag
        current_tag (str): target tag
        temp_repo_path (str): locally cloned repository path

    Returns:
        pd.DataFrame: DF of commits between two tags
    """
    # get the repo owner/name
    temp_repo_owner = temp_repo_path.split("/")[-2]
    temp_repo_name = temp_repo_path.split("/")[-1]

    # set the git.Git class for the repo
    temp_repo = git.Git(temp_repo_path)

    # obtain all commits
    temp_commits = pd.DataFrame(
        temp_repo.log(f"{prior_tag}...{current_tag}", "--pretty=oneline").split("\n"),
        columns=["raw_git_log"],
    )
    # set sha
    temp_commits["sha"] = temp_commits.apply(
        lambda x: x["raw_git_log"].split(" ")[0], axis=1
    )
    # set the message
    temp_commits["message"] = temp_commits.apply(
        lambda x: " ".join(x["raw_git_log"].split(" ")[1:]), axis=1
    )

    # get the full message
    temp_commits["full_message"] = temp_commits.apply(
        lambda x: get_full_commit_message(
            sha=x["sha"],
            temp_git=temp_repo,
        ),
        axis=1,
    )

    # add the normalized commit rank. A future feature. Add 1 so it matches length
    temp_commits["commit_rank"] = temp_commits.index + 1

    # normalize the commit rank based on the commits
    temp_commits["normalized_commit_rank"] = temp_commits.apply(
        lambda x: int(x["commit_rank"]) / len(temp_commits), axis=1
    )

    return temp_commits


def get_full_commit_message(sha: str, temp_git: git.Git) -> str:
    """Returns the full commit message for a given commit sha

    Args:
        sha (str): Target Sha
        temp_git (git.Git): git.Git repo

    Returns:
        str: The output message
    """
    message = (
        temp_git.log(f"{sha}", "--oneline", "--format=%H %s %b", "-n", "1")
        .split("\n")[0]
        .split(" ")
    )
    final_message = " ".join(message[1:])

    return final_message


from multiprocessing import Process, Queue
import time


def run_commit_local(queue, **kwargs):
    try:
        result = patchparser.github_parser_local.commit_local(**kwargs)
        queue.put(result)
    except Exception as e:
        queue.put(e)


def commit_local_with_timeout(timeout, **kwargs):
    queue = Queue()
    p = Process(target=run_commit_local, args=(queue,), kwargs=kwargs)
    p.start()
    p.join(timeout=timeout)

    if p.is_alive():
        p.terminate()
        p.join()
        return None  # 或者 raise TimeoutError("Operation timed out")

    result = queue.get()
    if isinstance(result, Exception):
        raise result
    return result


def git_diff(clone_path: str, commit_sha: str) -> dict:
    """Obtains the git diff information using patchparser
    Info: https://github.com/tdunlap607/patchparser

    Args:
        clone_path (str): Location of source code
        commit_sha (_type_): Target commit to parse

    Returns:
        (dict): Dictionary of git diff info
    """

    repo_owner = clone_path.split("/")[-3]
    repo_name = clone_path.split("/")[-2]

    # 使用示例
    try:
        diff = commit_local_with_timeout(
            timeout=3,  # 30秒超时
            repo_owner=repo_owner,
            repo_name=repo_name,
            sha=commit_sha,
            base_repo_path=clone_path,
        )
        if diff is None:
            print("操作超时，已跳过")
    except Exception as e:
        print(f"操作出错: {e}")

    return diff
