
"""
The primary function for finding VFCs for a given security advisory
Returns a set of five potential VFCs for the advisory
"""
import json  # 用于处理 JSON 数据
import pandas as pd  # 用于数据处理和分析
import torch  # 深度学习框架
import numpy as np  # 用于科学计算
import xgboost as xgb  # 梯度提升库
import os

from transformers import AutoConfig
from pathlib import Path  # 用于处理文件路径
from utils import osv_helper, git_helper  # 导入自定义工具模块
from features import vfc_identification, static_features, semantic_similarity  # 导入自定义特征模块
from datetime import datetime
gitee_token = "f4df8c3829e1d87e1aa03d4529af6b24"
def rank(advisory_path: str, clone_path: str, return_results=False, output_path=None):
    """Ranks commits in relevance to a given security advisory

    Args:
        advisory_path (str): Local path to a security advisory
        clone_path (str): Local path to clone a repository
        return_results (bool): Returns sorted commits in a pd.DataFrame
        output_path (str): Path to save results in a CSV form
    """
    # SET args
    GHSA_ID = advisory_path  # 安全公告的路径作为 GHSA ID
    CLONE_DIRECTORY = clone_path  # 克隆仓库的本地目录

    # dynamically set variables
    PARENT_PATH = f"{str(Path(__file__).resolve().parent.parent)}/"  # 获取项目父目录路径
    DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")  # 选择计算设备，优先使用 GPU

    #####################################################################################
    # load/parse report
    with open(f"{PARENT_PATH}vfcfinder/data/osv_schema.json", "r") as f:
        osv_schema = json.load(f)  # 加载 OSV 模式文件
        f.close()

    # parse the JSON
    parsed = osv_helper.parse_osv(
        osv_json_filename=f"{GHSA_ID}",  # 解析指定路径的 OSV 安全公告
        osv_schema=osv_schema,
    )

    # create a dataframe that's easier to handle
    parsed_df = parsed[1].copy()  # 将解析结果的一部分转换为 DataFrame

    # identify the repo_url
    repo_url = parsed[0]["reference_url"][parsed[0]["reference_type"].index("PACKAGE")]  # 获取仓库的 URL



    # extract the base repo owner/name
    repo_owner = repo_url.split("/")[-2]  # 提取仓库所有者名称
    repo_name = repo_url.split("/")[-1]  # 提取仓库名称

    # set a clone path
    CLONE_PATH = f"{CLONE_DIRECTORY}{repo_owner}/{repo_name}/"  # 设置克隆仓库的完整路径

    #####################################################################################
    # clone repo
    print(f"\nCloning repository: {repo_owner}/{repo_name}")
    git_helper.clone_repo(
        repo_owner=repo_owner, repo_name=repo_name, clone_path=CLONE_DIRECTORY  # 克隆指定的 GitHub 仓库
    )

    #####################################################################################
    # find fixed/vulnerable version
    fix_tag = parsed[1].fixed.iloc[-1]  # 获取修复版本的标签

    #####################################################################################
    # load the OWASP Lookup table and map
    owasp_data = pd.read_csv(
        f"{PARENT_PATH}/vfcfinder/utils/data_lookup/owasp2021_map.csv"  # 加载 OWASP 映射表
    )
    owasp_data["cwe_ids"] = owasp_data.apply(lambda x: f"CWE-{x['cwe']}", axis=1)  # 生成 CWE ID 列
    owasp_map = vfc_identification.get_owasp_label_map()  # 获取 OWASP 标签映射

    # set the owasp_label from training
    owasp_data = pd.merge(
        owasp_data,
        owasp_map[["rank", "label"]],
        left_on="owasp_rank",
        right_on="rank",
        how="left",  # 将 OWASP 数据与映射表合并
    )

    # set the parsed owasp_label
    parsed_df = parsed_df.merge(
        owasp_data[["owasp_rank", "cwe_ids", "label"]], on="cwe_ids", how="left"  # 将解析结果与 OWASP 数据合并
    )

    #####################################################################################
    # get the prior and fixed tag of the local repo
    tags = git_helper.get_prior_tag(
        repo_owner=repo_owner,
        repo_name=repo_name,
        clone_path=CLONE_DIRECTORY,
        target_tag=fix_tag,  # 获取指定标签的前一个标签
    )

    # set the vulnerable/fixed tags
    repo_vuln_tag = tags["prior_tag"]  # 设置漏洞版本标签
    repo_fix_tag = tags["current_tag"]  # 设置修复版本标签

    #####################################################################################
    # load all commits
    commits = git_helper.get_commits_between_tags(
        prior_tag=repo_vuln_tag,
        current_tag=repo_fix_tag,
        temp_repo_path=CLONE_PATH,  # 获取两个标签之间的所有提交记录
    )

    #####################################################################################
    # generate features
    # patchparser for each commit
    commits_diff = pd.DataFrame()  # 初始化提交差异的 DataFrame

    # get the diff of each commit
    for idx, row in commits.iterrows():
        print(f"Obtaining diff for commit {idx+1}/{len(commits)} || {row['sha'][:7]}")
        temp_diff = git_helper.git_diff(
            clone_path=CLONE_PATH,
            commit_sha=row["sha"],  # 获取每个提交的差异信息
        )
        temp_diff_df = pd.DataFrame(temp_diff)

        commits_diff = pd.concat([commits_diff, temp_diff_df])  # 合并差异信息

    #####################################################################################
    # vfc_identification
    print("\nGenerating VFC probability inference for each commit...")

    commit_vfc_data = vfc_identification.load_ghsa_vfc_data(
        vuln_file=commits_diff,
        class_name="vfc_label",
        group_level=["message", "file_type"],  # 加载 VFC 数据
    )

    commit_vfc_data["label"] = 0  # 初始化标签列

    tokenizer, model = vfc_identification.load_vfc_identification_model()  # 加载 VFC 识别模型和分词器

    commit_dataloader = vfc_identification.convert_df_to_dataloader(
        tokenizer=tokenizer,
        temp_df=commit_vfc_data,
        text="message",
        text_pair="file_pure_modified_code",
        target="label",
        batch_size=32,  # 将数据转换为数据加载器
    )

    model.to(DEVICE)  # 将模型移动到指定设备

    preds, probs = vfc_identification.validation_model_single_epoch(
        model,
        val_dataloader=commit_dataloader,
        device=DEVICE,
        binary_classification=True,
        class_weights=None,  # 进行单轮验证，获取预测结果和概率
    )

    commit_vfc_data["vfc_prob"] = probs  # 添加 VFC 概率列

    # merge the probabilities back to the commits
    commits = pd.merge(
        commits, commit_vfc_data[["sha", "vfc_prob"]], on=["sha"], how="left"  # 将 VFC 概率合并到提交记录中
    )

    commits["vfc_prob"] = commits.vfc_prob.fillna(0)  # 处理缺失值

    # delete the model
    del model  # 删除模型以释放内存

    #####################################################################################
    # vfc_type
    print("\nGenerating VFC type inference for each commit...")
    tokenizer, model = vfc_identification.load_vfc_type_model()  # 加载 VFC 类型模型和分词器

    model.to(DEVICE)  # 将模型移动到指定设备

    type_preds, type_probs = vfc_identification.validation_model_single_epoch(
        model,
        val_dataloader=commit_dataloader,
        device=DEVICE,
        binary_classification=False,
        class_weights=None,  # 进行单轮验证，获取 VFC 类型预测结果和概率
    )

    commit_vfc_data["vfc_type"] = list(type_probs)  # 添加 VFC 类型列

    commit_vfc_data["vfc_type_top_5"] = commit_vfc_data.apply(
        lambda x: np.array(list(x["vfc_type"])).argsort()[-5:][::-1].tolist(),
        axis=1,  # 获取 VFC 类型概率前 5 的索引
    )

    commit_vfc_data["vfc_type_top_1"] = commit_vfc_data.apply(
        lambda x: True if parsed_df.iloc[0].label == x["vfc_type_top_5"][0] else False,
        axis=1,  # 判断是否为 VFC 类型概率第 1 的标签
    )

    commit_vfc_data["vfc_type_top_5"] = commit_vfc_data.apply(
        lambda x: True if parsed_df.iloc[0].label in x["vfc_type_top_5"] else False,
        axis=1,  # 判断是否在 VFC 类型概率前 5 的标签中
    )

    # merge the probabilities back to the commits
    commits = pd.merge(
        commits,
        commit_vfc_data[["sha", "vfc_type_top_1", "vfc_type_top_5"]],
        on=["sha"],
        how="left",  # 将 VFC 类型信息合并到提交记录中
    )

    commits["vfc_type_top_1"] = commits.vfc_type_top_1.fillna(False)  # 处理缺失值
    commits["vfc_type_top_5"] = commits.vfc_type_top_5.fillna(False)  # 处理缺失值

    del model  # 删除模型以释放内存

    #####################################################################################
    # semantic similarity
    print("\n")

    print("Generating semantic similarity scores...")

    # batch all the commits for a semantic similarity
    commits["semantic_similarity"] = semantic_similarity.semantic_similarity_batch(
        temp_commits=commits.copy(), advisory_details=parsed[0]["details"]  # 批量计算语义相似度
    )

    # merge similarity scores back to commits
    # commits = commits.merge(similarity_df, on=["sha"], how="left")

    #####################################################################################
    # cve/ghsa in message
    commits["cve_in_message"] = commits.apply(
        lambda x: static_features.cve_in_commit_message(
            x["full_message"], parsed[0]["aliases"][0]
        ),
        axis=1,  # 判断提交消息中是否包含 CVE ID
    )

    commits["ghsa_in_message"] = commits.apply(
        lambda x: static_features.ghsa_in_commit_message(
            x["full_message"], parsed[0]["id"]
        ),
        axis=1,  # 判断提交消息中是否包含 GHSA ID
    )

    #####################################################################################
    # commit rank
    ranking_model = xgb.Booster()  # 初始化 XGBoost 模型
    ranking_model.load_model(
        f"{PARENT_PATH}/vfcfinder/models/xgboost_model_20230618.json"  # 加载预训练的 XGBoost 模型
    )

    # set the features to use
    features = [
        "normalized_commit_rank",
        "vfc_prob",
        "vfc_type_top_1",
        "vfc_type_top_5",
        "semantic_similarity",
        "ghsa_in_message",
        "cve_in_message",  # 设置用于排名的特征
    ]
    # rename from the original trained model
    ranking_model.feature_names = features  # 设置模型的特征名称

    # create a new dataset for the features data
    ranking_data = commits[features].reset_index(drop=True)  # 创建特征数据集

    # convert labels to ints for XGBoost
    ranking_data["vfc_type_top_1"] = ranking_data["vfc_type_top_1"].astype(int)  # 将布尔类型转换为整数类型
    ranking_data["vfc_type_top_5"] = ranking_data["vfc_type_top_5"].astype(int)  # 将布尔类型转换为整数类型
    ranking_data["ghsa_in_message"] = ranking_data["ghsa_in_message"].astype(int)  # 将布尔类型转换为整数类型
    ranking_data["cve_in_message"] = ranking_data["cve_in_message"].astype(int)  # 将布尔类型转换为整数类型

    # convert to a DMatrix, XGBoost speed
    d_ranking = xgb.DMatrix(ranking_data)  # 将数据转换为 XGBoost 的 DMatrix 格式

    # make the predictions
    ranked_data_probs = ranking_model.predict(d_ranking)  # 进行预测

    # merge back to the commits DF
    ranked_data_probs_list = list(ranked_data_probs)
    commits["ranking_prob"] = ranked_data_probs_list  # 将预测结果合并到提交记录中

    # make final ranked prediction
    commits = commits.sort_values("ranking_prob", ascending=False).reset_index(
        drop=True  # 按排名概率降序排序
    )

    # print the top ranked commits
    print(f"\nRanked commits in relevance to advisory {GHSA_ID}:")
    for idx, row in commits[:5].iterrows():
        print(
            f"Rank {idx+1} || "
            f" SHA: {row.sha[:7]} || "
            f" Commit Message: {row.message[:40]} || "
            f"VFC Prob: {round(row.vfc_prob, 2)}"  # 打印排名前 5 的提交记录
        )

    # save results
    if output_path is not None:
        commits.to_csv(output_path, encoding='utf-8', index=False)  # 将结果保存为 CSV 文件

    # return results for later use
    if return_results:
        return commits  # 返回排序后的提交记录

#
# def extract_diff(repo_url: str, clone_path: str, git_token:str,return_results=False, output_path=None):
#     """Ranks commits in relevance to a given security advisory
#
#     Args:
#         repo_url (str): Local path to a security advisory
#         clone_path (str): Local path to clone a repository
#         return_results (bool): Returns sorted commits in a pd.DataFrame
#         output_path (str): Path to save results in a CSV form
#     """
#
#     CLONE_DIRECTORY = clone_path  # 克隆仓库的本地目录
#
#     # dynamically set variables
#     PARENT_PATH = f"{str(Path(__file__).resolve().parent.parent)}/"  # 获取项目父目录路径
#     DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")  # 选择计算设备，优先使用 GPU
#
#     #####################################################################################
#     # load/parse report
#     with open(f"{PARENT_PATH}vfcfinder/data/osv_schema.json", "r") as f:
#         osv_schema = json.load(f)  # 加载 OSV 模式文件
#         f.close()
#
#
#     # extract the base repo owner/name
#     repo_type = repo_url.split("/")[-3]
#     repo_owner = repo_url.split("/")[-2]  # 提取仓库所有者名称
#     repo_name = repo_url.split("/")[-1]  # 提取仓库名称
#
#     # set a clone path
#     CLONE_PATH = f"{CLONE_DIRECTORY}{repo_owner}/{repo_name}/"  # 设置克隆仓库的完整路径
#
#     #####################################################################################
#     # clone repo
#     print(f"\nCloning repository: {repo_owner}/{repo_name}")
#     clone_flag = git_helper.clone_repo_with_token(
#         repo_type=repo_type,repo_owner=repo_owner, repo_name=repo_name, clone_path=CLONE_DIRECTORY,token=git_token # 克隆指定的 GitHub 仓库
#     )
#     if not clone_flag:
#         print("无法获取该仓库")
#         return pd.DataFrame()
#     ##################
#     commits = git_helper.get_recent_commits(
#         temp_repo_path=CLONE_PATH,# 新增函数获取所有提交
#         days=1
#     )
#
#     if(commits.empty):
#         print("仓库没有提交记录")
#         return pd.DataFrame()
#     #####################################################################################
#     # generate features
#     commits_diff = pd.DataFrame()  # 初始化提交差异的 DataFrame
#
#     # get the diff of each commit
#     for idx, row in commits.iterrows():
#         # print(f"Obtaining diff for commit {idx+1}/{len(commits)} || {row['sha'][:7]}")
#         temp_diff = git_helper.git_diff(
#             clone_path=CLONE_PATH,
#             commit_sha=row["sha"],  # 获取每个提交的差异信息
#         )
#         temp_diff_df = pd.DataFrame(temp_diff)
#
#         commits_diff = pd.concat([commits_diff, temp_diff_df])  # 合并差异信息
#
#     #####################################################################################
#
#     # 在获取diff数据后添加：
#     commits_diff.to_csv("debug_commits_diff_raw.csv", index=False)
#
#
#     return commits_diff

def extract_diff(repo_url: str, clone_path: str, git_token: str, return_results=False, output_path=None):
    """ commits in relevance to a given security advisory

    Args:
        repo_url (str): Local path to a security advisory
        clone_path (str): Local path to clone a repository
        git_token (str): Git access token
        return_results (bool): Returns sorted commits in a pd.DataFrame
        output_path (str): Path to save results in a CSV form
    Returns:
        pd.DataFrame: DataFrame containing commit diffs or empty DataFrame if failed
    """
    try:
        CLONE_DIRECTORY = clone_path

        # extract the base repo owner/name
        repo_type = repo_url.split("/")[-3]
        repo_owner = repo_url.split("/")[-2]
        repo_name = repo_url.split("/")[-1].replace('.git', '')  # Ensure .git is removed if present

        # set a clone path
        CLONE_PATH = f"{CLONE_DIRECTORY}{repo_owner}/{repo_name}/"

        #####################################################################################
        # clone repo
        print(f"\nCloning repository: {repo_owner}/{repo_name}")
        try:
            clone_flag = git_helper.clone_repo_with_token(
                repo_type=repo_type,
                repo_owner=repo_owner,
                repo_name=repo_name,
                clone_path=CLONE_DIRECTORY,
                token=git_token
            )
            if not clone_flag:
                print(f"无法获取该仓库 {repo_owner}/{repo_name}")
                return pd.DataFrame()
        except Exception as e:
            print(f"克隆仓库 {repo_owner}/{repo_name} 时出错: {str(e)}")
            return pd.DataFrame()

        ##################
        try:
            commits = git_helper.get_recent_commits(
                temp_repo_path=CLONE_PATH,
                days=46
                # 8-1  to 9-15
            )
            if commits.empty:
                print(f"仓库 {repo_owner}/{repo_name} 没有提交记录")
                return pd.DataFrame()
        except Exception as e:
            print(f"获取提交记录时出错 {repo_owner}/{repo_name}: {str(e)}")
            return pd.DataFrame()

        #####################################################################################
        # generate features
        commits_diff = pd.DataFrame()

        # get the diff of each commit
        for idx, row in commits.iterrows():
            try:
                print("row[sha]:",row["sha"])

                temp_diff = git_helper.git_diff(
                    clone_path=CLONE_PATH,
                    commit_sha=row["sha"],
                )

                if temp_diff is None:
                    print(f"获取提交 {row['sha'][:7]} 的差异失败，跳过")
                    continue
                temp_diff_df = pd.DataFrame(temp_diff)
                commits_diff = pd.concat([commits_diff, temp_diff_df])
            except Exception as e:
                print(f"处理提交 {row['sha'][:7]} 时出错: {str(e)}")
                continue  # 跳过当前提交，继续处理下一个

        # 保存调试信息
        if output_path:
            try:
                commits_diff.to_csv(output_path, index=False)
            except Exception as e:
                print(f"保存结果到 {output_path} 时出错: {str(e)}")

        return commits_diff

    except Exception as e:
        print(f"处理仓库 {repo_url} 时发生未捕获的异常: {str(e)}")
        return pd.DataFrame()
def save_data_with_version(output_path: str, output_df: pd.DataFrame):
    """
    智能保存数据文件（自动处理版本冲突）

    参数:
        output_path: 目标路径（必须包含.json或.csv后缀）
        output_df: 要保存的DataFrame
    """
    # 标准化路径处理
    output_path = Path(output_path)
    os.makedirs(output_path.parent, exist_ok=True)

    # 生成带版本号的新路径（如果文件已存在）
    if output_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = output_path.stem  # 获取文件名（不含后缀）
        suffix = output_path.suffix  # 获取文件后缀
        new_name = f"{stem}_{timestamp}{suffix}"
        output_path = output_path.with_name(new_name)

    # 根据后缀保存文件
    if output_path.suffix == '.json':
        output_data = output_df.to_dict('records')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
    elif output_path.suffix == '.csv':
        output_df.to_csv(output_path, index=False, encoding='utf-8')
    else:
        raise ValueError("仅支持 .json 或 .csv 格式")

    print(f"数据已保存到: {output_path}")
def rank2( return_results=False, output_path=None,commit_diff=None):
    """Ranks commits in relevance to a given security advisory

    Args:
        repo_url (str): Local path to a security advisory
        clone_path (str): Local path to clone a repository
        return_results (bool): Returns sorted commits in a pd.DataFrame
        output_path (str): Path to save results in a CSV form
    """
    classification_model_path = "dataset_built/dataset2/vfc_finetuned_8-31/best_model"
    # dynamically set variables
    PARENT_PATH = f"{str(Path(__file__).resolve().parent.parent)}/"  # 获取项目父目录路径
    # 强制指定 GPU 0
    # if torch.cuda.is_available():
    #     torch.cuda.set_device(0)  # 显式设置当前设备为 GPU 0
    #     DEVICE = torch.device("cuda:0")
    #     print(f"Using GPU {torch.cuda.current_device()}: {torch.cuda.get_device_name(0)}")
    # else:
    #     DEVICE = torch.device("cpu")
    #     print("Using CPU")

    DEVICE = torch.device("cpu")
    print("Using CPU")

    commit_vfc_data = vfc_identification.load_ghsa_vfc_data(
        vuln_file=commit_diff,
        class_name="vfc_label",
        group_level=["message", "file_type"],  # 加载 VFC 数据
    )

    commit_vfc_data["label"] = 0  # 初始化标签列

    original_config = AutoConfig.from_pretrained("tdunlap607/vfc-identification")
    finetuned_config = AutoConfig.from_pretrained(classification_model_path)

    print("分类数是否一致:", original_config.num_labels == finetuned_config.num_labels)  # 必须为True
    print("模型类型是否一致:", original_config.model_type == finetuned_config.model_type)  # 必须为True


    tokenizer, model = vfc_identification.load_finetuned_vfc_identification_model(classification_model_path)  # 加载 VFC 识别模型和分词器
    # tokenizer, model = vfc_identification.load_vfc_type_model()  # 加载 VFC 类型模型和分词器


    commit_dataloader = vfc_identification.convert_df_to_dataloader(
        tokenizer=tokenizer,
        temp_df=commit_vfc_data,
        text="message",
        text_pair="file_pure_modified_code",
        target="label",
        batch_size=32,  # 将数据转换为数据加载器
    )


    model.to(DEVICE)  # 将模型移动到指定设备

    preds, probs = vfc_identification.validation_model_single_epoch2(
        model,
        val_dataloader=commit_dataloader,
        device=DEVICE,
        binary_classification=True,
        class_weights=None,  # 进行单轮验证，获取预测结果和概率
    )

    if probs.ndim == 2:  # 如果是二维概率矩阵
        commit_vfc_data["vfc_prob"] = probs[:, 1]  # 只取正类（索引1）的概率
    else:
        commit_vfc_data["vfc_prob"] = probs  # 如果已经是一维数组


    # merge the probabilities back to the commits
    commits = pd.merge(
        commit_diff, commit_vfc_data[["sha", "vfc_prob"]], on=["sha"], how="left"  # 将 VFC 概率合并到提交记录中
    )

    commits["vfc_prob"] = commits.vfc_prob.fillna(0)  # 处理缺失值
    commits = commits.sort_values("vfc_prob", ascending=False).reset_index(drop=True)

    # 示例：替换无效字符
    commits = commits.apply(
        lambda x: x.encode('utf-8', 'ignore').decode('utf-8') if isinstance(x, str) else x)

    output_df = pd.DataFrame(commits)
    # Determine output path
    if output_path is None:
        output_path = f"{PARENT_PATH}/results/commit_ranking.json"
    else:
        output_path = f"{PARENT_PATH}/results/{output_path}"


    save_data_with_version(output_path, output_df)

    print(f"\nResults saved to: {output_path}")
    del model  # 删除模型以释放内存

    # return results for later use
    if return_results:
        return commits  # 返回排序后的提交记录

def rank3(return_results=False, output_path=None, input_data=None):
    """Ranks commits in relevance to a given security advisory

    Args:
        repo_url (str): Local path to a security advisory
        clone_path (str): Local path to clone a repository
        return_results (bool): Returns sorted commits in a pd.DataFrame
        output_path (str): Path to save results in a CSV form
    """
    classification_model_path = "dataset_built/dataset2/vfc_finetuned_8-31/best_model"

    # dynamically set variables
    PARENT_PATH = f"{str(Path(__file__).resolve().parent.parent)}/"  # 获取项目父目录路径
    # 强制指定 GPU 0
    # if torch.cuda.is_available():
    #     torch.cuda.set_device(0)  # 显式设置当前设备为 GPU 0
    #     DEVICE = torch.device("cuda:0")
    #     print(f"Using GPU {torch.cuda.current_device()}: {torch.cuda.get_device_name(0)}")
    # else:
    #     DEVICE = torch.device("cpu")
    #     print("Using CPU")

    DEVICE = torch.device("cpu")
    print("Using CPU")

    original_config = AutoConfig.from_pretrained("tdunlap607/vfc-identification")
    finetuned_config = AutoConfig.from_pretrained(classification_model_path)

    print("分类数是否一致:", original_config.num_labels == finetuned_config.num_labels)  # 必须为True
    print("模型类型是否一致:", original_config.model_type == finetuned_config.model_type)  # 必须为True

    tokenizer, model = vfc_identification.load_finetuned_vfc_identification_model(
        classification_model_path)  # 加载 VFC 识别模型和分词器
    # tokenizer, model = vfc_identification.load_vfc_type_model()  # 加载 VFC 类型模型和分词器

    commit_dataloader = vfc_identification.convert_df_to_dataloader(
        tokenizer=tokenizer,
        temp_df=input_data,
        text="message",
        text_pair="input",
        target="label",
        batch_size=32,  # 将数据转换为数据加载器
    )

    model.to(DEVICE)  # 将模型移动到指定设备

    preds, probs = vfc_identification.validation_model_single_epoch2(
        model,
        val_dataloader=commit_dataloader,
        device=DEVICE,
        binary_classification=True,
        class_weights=None,  # 进行单轮验证，获取预测结果和概率
    )

    if probs.ndim == 2:  # 如果是二维概率矩阵
        input_data["vfc_prob"] = probs[:, 1]  # 只取正类（索引1）的概率
    else:
        input_data["vfc_prob"] = probs  # 如果已经是一维数组

    # # merge the probabilities back to the commits
    # commits = pd.merge(
    #     input_data, input_data[["sha", "vfc_prob"]], on=["sha"], how="left"  # 将 VFC 概率合并到提交记录中
    # )

    # commits["vfc_prob"] = commits.vfc_prob.fillna(0)  # 处理缺失值
    # commits = commits.sort_values("vfc_prob", ascending=False).reset_index(drop=True)


    # 示例：替换无效字符
    # commits = commits.apply(
    #     lambda x: x.encode('utf-8', 'ignore').decode('utf-8') if isinstance(x, str) else x)

    output_df = pd.DataFrame(input_data)
    # Determine output path
    if output_path is None:
        output_path = f"{PARENT_PATH}vfcfinder/results/commit_ranking.json"
    else:
        output_path = f"{PARENT_PATH}vfcfinder/results/{output_path}"
    # Create directory if not exists

    save_data_with_version(output_path, output_df)

    print(f"\nResults saved to: {output_path}")

    # delete the model
    del model  # 删除模型以释放内存
    # return results for later use

