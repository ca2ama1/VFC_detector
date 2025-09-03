"""
Provides the VFC identification probability
"""
import pandas as pd
import os
import torch

from transformers import AutoModel, AutoConfig
from transformers import (
    RobertaForSequenceClassification,
    AutoTokenizer
)
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
import numpy as np
from tqdm import tqdm



def get_owasp_label_map() -> pd.DataFrame:
    """Custom mapping of the OWASP labels for our trained XGBoost Model

    Returns:
        pd.DataFrame: Custom mapping of OWASP labels
    """
    
    # the order of the label is mixed because we didn't have A06 in training data
    owasp_list = [
        ["Broken Access Control", "A01", 0, 1],
        ["Cryptographic Failures", "A02", 1, 2],
        ["Injection", "A03", 2, 3],
        ["Insecure Design", "A04", 3, 4],
        ["Security Misconfiguration", "A05", 4, 5],
        ["Vulnerable and Outdated Components", "A06", 10, 6],
        ["Identification and Authentication Failures", "A07", 5, 7],
        ["Software and Data Integrity Failures", "A08", 6, 8],
        ["Security Logging and Monitoring Failures", "A09", 7, 9],
        ["Server-Side Request Forgery", "A10", 8, 10],
        ["Other", "Other", 9, 11],
    ]

    # convert to a dataframe
    owasp_map = pd.DataFrame(
        owasp_list, columns=["name", "short_name", "label", "rank"]
    )

    return owasp_map


def pure_modified_code(temp_raw_patch: str) -> str:
    """Obtains +/- aspects of the git diff
    Split the code so we can parse line by line

    Args:
        temp_raw_patch (str): Raw patch string from patchparser

    Returns:
        str: Cleaned concat of the modified code
    """
    # make sure it's a string
    temp_raw_patch = str(temp_raw_patch)
    split_code = temp_raw_patch.splitlines()

    temp_modified_code = ""

    # obtain the modified/removed/added code
    for line in split_code:
        if line.startswith("-") or line.startswith("+"):
            temp_modified_code = temp_modified_code + " " + line

    return temp_modified_code


def load_ghsa_vfc_data(
        vuln_file: pd.DataFrame, class_name: str, group_level: list
) -> pd.DataFrame:
    """Creates a clean pd.DataFrame of the commits to analyze

    Args:
        vuln_file (str): Commits
        class_name (str): 
        group_level (list): Granularity to make predictions

    Returns:
        pd.DataFrame: Clean DF of commits
    """
    # 打印输入数据的形状和前几行样例
    print("输入数据形状:", vuln_file.shape)
    print("输入数据样例:", vuln_file.head())

    # 创建分组级别（用于后续聚合）
    unique_groups = ["repo_owner", "repo_name", "sha"] + group_level
    # 验证集专用
    # unique_groups = ["repo", "sha"] + group_level


    # 检查输入数据是否为空
    if vuln_file.empty:
        raise ValueError("输入数据 vuln_file 为空，请检查数据源！")

    # 复制输入数据以避免修改原始数据
    vuln_commits = vuln_file

    # 定义重要编程语言的扩展名映射
    important_languages = {
        "c": "C/C++",
        "cpp": "C/C++",
        "cc": "C/C++",
        "h": "C/C++",
        "java": " Java",
        "py": "Python",
        "go": "Go",
        "php": "PHP",
        "rb": "Ruby",
        "ts": "TypeScript",
        "js": "JavaScript",
        "cs": "C#",
        "rs": "Rust",
    }

    # 标记重要语言文件（True/False）
    vuln_commits["important_language"] = vuln_commits.apply(
        lambda x: True if x["file_extension"] in important_languages else False, axis=1
    )

    # 只保留重要语言的文件
    vuln_commits = vuln_commits[vuln_commits["important_language"] == True].reset_index(
        drop=True
    )
    print("过滤重要语言后的commit矩阵形状：", vuln_commits.shape)

    # 检查过滤后数据是否为空
    if vuln_commits.empty:
        print("\n没有检测到重要语言的代码文件")
    else:
        # 添加漏洞修复提交标签
        vuln_commits["vfc_label"] = True
        # 添加文件类型列
        vuln_commits["file_type"] = vuln_commits["file_extension"]

        # 重置索引
        commits = vuln_commits.reset_index(drop=True)

        # 创建唯一ID（组合仓库所有者、仓库名和提交SHA）
        commits["id"] = commits.apply(
            lambda x: f"{x['repo_owner']}_{x['repo_name']}_{x['sha']}", axis=1
            # lambda x: f"{x['repo']}_{x['sha']}", axis=1
        )

        # 提取纯净的修改代码（通过raw_patch处理）
        commits["pure_modified_code"] = commits.apply(
            lambda x: pure_modified_code(x["raw_patch"]), axis=1
        )

        # 定义聚合分组（包含纯净代码）
        agg_group = unique_groups + ["pure_modified_code"]
        # 按分组聚合纯净代码（合并同一次提交的多个文件修改）
        commits["file_pure_modified_code"] = (
            commits[agg_group]
            .groupby(unique_groups)["pure_modified_code"]
            .transform(lambda x: " ".join(x))
        )

        # 去重（保留每个分组的第一个记录）
        commits = commits.drop_duplicates(subset=unique_groups, keep="first")

        # 移除关键字段为空的记录
        commits_clean = commits.dropna(
            subset=["vfc_label", "file_pure_modified_code", "message"]
        )

        # 再次去重（基于分组和标签）
        commits_clean = commits_clean.drop_duplicates(
            subset=unique_groups + ["vfc_label"], keep="first"
        )

        # 确保关键字段为字符串类型
        commits_clean["message"] = commits_clean["message"].astype(str)
        commits_clean["file_pure_modified_code"] = commits_clean[
            "file_pure_modified_code"
        ].astype(str)

        # 计算纯净代码长度（用于后续过滤）
        temp = commits_clean.apply(lambda x: len(x["file_pure_modified_code"]), axis=1)

        # 过滤掉空内容的记录
        commits_clean["agg_length"] = temp
        commits_clean = commits_clean[commits_clean["agg_length"] > 0]

        # 标签编码（将布尔标签转为数值）
        le = LabelEncoder()
        labels = le.fit_transform(commits_clean["vfc_label"])
        commits_clean["label"] = labels

        # One-Hot编码（用于机器学习）
        enc = OneHotEncoder(handle_unknown="ignore")
        transformed = enc.fit_transform(commits_clean[["label"]])
        commits_clean["onehot_label"] = transformed.toarray().tolist()

        # 选择最终输出的列
        commits_clean = commits_clean[
            unique_groups
            + ["id", "file_pure_modified_code", "label", "onehot_label", class_name]
            ].reset_index(drop=True)

        # 按ID排序
        commits_clean = commits_clean.sort_values(by="id").reset_index(drop=True)

    return commits_clean

def load_vfc_identification_model():
    """Loads the tokenizer/model from huggingface to predict if a commit is a VFC
    https://huggingface.co/tdunlap607/vfc-identification
    """
    # load tokenizer
    tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")

    # loads the model
    model = AutoModel.from_pretrained(
        "tdunlap607/vfc-identification", trust_remote_code=True
    )

    return tokenizer, model


def load_finetuned_vfc_identification_model(local_model_dir):
    """Loads the tokenizer and model from local directory to predict if a commit is a VFC

    Args:
        local_model_dir (str): Path to the directory containing the locally saved model
    Returns:
        tuple: (tokenizer, model) pair
    """
    # 确保目录存在
    if not os.path.exists(local_model_dir):
        raise FileNotFoundError(f"Model directory not found: {local_model_dir}")

    # 加载tokenizer (使用原始CodeBERT的tokenizer)
    tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")

    # 加载本地训练好的模型
    # model = AutoModelForSequenceClassification.from_pretrained(local_model_dir)
    model = RobertaForSequenceClassification.from_pretrained(local_model_dir)

    return tokenizer, model

def load_vfc_type_model():
    """Loads the tokenizer/model from huggingface to predict if a commit is a VFC
    https://huggingface.co/tdunlap607/vfc-type
    """
    # load tokenizer
    tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")

    # loads the model
    model = AutoModel.from_pretrained("tdunlap607/vfc-type", trust_remote_code=True)

    return tokenizer, model


class ConvertDataset(Dataset):
    def __init__(
        self, df, tokenizer, text_name: str, text_pair_name: str, target_label: str
    ):
        self.df_data = df
        self.tokenizer = tokenizer
        self.text_name = text_name  # e.g., message
        self.text_pair_name = text_pair_name  # e.g., file_pure_modified_code
        self.target_label = target_label  # e.g., onehot_label

    def __getitem__(self, index):
        # get the sentence from the dataframe
        text = self.df_data.loc[index, self.text_name]
        text_pair = self.df_data.loc[index, self.text_pair_name]

        # Process the sentence
        # ---------------------
        # Tokenize the sentence using the above tokenizer from BERT
        # Special tokens will add [CLS]parent_sentence[SEP]child_sentence[SEP]
        # Return attenion masks
        # https://huggingface.co/docs/transformers/v4.22.2/en/internal/tokenization_utils#transformers.PreTrainedTokenizerBase.encode_plus
        # encoded_dict = self.tokenizer.encode_plus(
        # encode_plus is deprecated
        # https://huggingface.co/docs/transformers/v4.24.0/en/internal/tokenization_utils#transformers.PreTrainedTokenizerBase.__call__
        encoded_dict = self.tokenizer.__call__(
            text=text,
            text_pair=text_pair,
            add_special_tokens=True,
            padding="max_length",
            truncation=True,
            return_attention_mask=True,
            return_token_type_ids=True,
            return_tensors="pt",
        )

        # each of these are in the form of a pt
        padded_token_list = encoded_dict["input_ids"][0]
        att_mask = encoded_dict["attention_mask"][0]
        token_type_ids = encoded_dict["token_type_ids"][0]

        # Convert the target to a torch tensor
        target = torch.tensor(self.df_data.loc[index, self.target_label])

        sample = (padded_token_list, att_mask, token_type_ids, target)

        return sample

    def __len__(self):
        return len(self.df_data)


def convert_df_to_dataloader(
    tokenizer,
    temp_df: pd.DataFrame,
    text: str,
    text_pair: str,
    target: str,
    batch_size: int,
):
    """_summary_

    Args:
        tokenizer : Loaded tokenizer
        temp_df (pd.DataFrame): Commits DF
        text (str): Commit message
        text_pair (str): Code diff
        target (str): Target Label
        batch_size (int): Batch size

    Returns:
        dataloader for downstream use
    """
    # Does the tokenization
    temp_data = ConvertDataset(
        df=temp_df,
        tokenizer=tokenizer,
        text_name=text,
        text_pair_name=text_pair,
        target_label=target,
    )

    # No need to shuffle as the data has already been shuffled in the splits
    temp_dataloader = torch.utils.data.DataLoader(
        temp_data, batch_size=batch_size, num_workers=8, shuffle=False
    )

    return temp_dataloader



def validation_model_single_epoch(
    model,
    val_dataloader,
    device: str,
    binary_classification=False,
    class_weights=None,
):
    """_summary_

    Args:
        model : Loaded HF model
        val_dataloader (_type_): convert_df_to_dataloader()
        device (str): Device type
        binary_classification (bool, optional): Defaults to False.
        class_weights (list, optional): Class weights. Defaults to None.

    Returns:
        Model predictions (prediction, raw_prediction)
    """

    # place model in evaluation mode
    model.eval()

    # arrays to hold predictions and
    val_prediction_labels = np.array([])
    if class_weights is None:
        # TODO: Better way to handle the length of this when we don't pass class weights
        if binary_classification:
            val_raw_probs_preds = np.array([]).reshape(0, 2)
        else:
            val_raw_probs_preds = np.array([]).reshape(0, 10)
    else:
        val_raw_probs_preds = np.array([]).reshape(
            0, len(class_weights)
        )  # reshape to handle better appends

    with torch.no_grad():
        # create a progress bar
        val_bar = tqdm(enumerate(val_dataloader), total=len(val_dataloader))

        # loop through each batch
        for i, val_batch in val_bar:
            # obtain all the various ids/masks/tokens/labels from the train_dataloader
            val_batch_input_ids = val_batch[0].to(device)
            val_batch_attention_mask = val_batch[1].to(device)
            val_batch_token_type_ids = val_batch[2].to(device)
            # val_batch_labels = val_batch[3].to(device)

            # Get the model output
            val_output = model(
                input_ids=val_batch_input_ids,
                attention_mask=val_batch_attention_mask,
                token_type_ids=val_batch_token_type_ids,
            )

            # collect raw probabilities for each class of the prediction. Helps later when aggregating results to commit-level
            if binary_classification:
                # no need for softmax on already Sigmoid values for probs
                val_raw_probs = val_output.cpu().detach().numpy()
                val_raw_probs_preds = np.append(val_raw_probs_preds, val_raw_probs)
                # for binary if the value is above 0.5 then 1, else 0
                output_label = (val_raw_probs > 0.5).squeeze(1).astype(int)

            else:
                val_raw_probs = torch.softmax(val_output, dim=1).cpu().detach().numpy()
                val_raw_probs_preds = np.append(
                    val_raw_probs_preds, val_raw_probs, axis=0
                )  # axis=0 keeps the shape of the probs

                output_label = np.argmax(val_raw_probs, axis=1)

            val_prediction_labels = np.append(val_prediction_labels, output_label)

        return val_prediction_labels, val_raw_probs_preds


def validation_model_single_epoch2(
        model,
        val_dataloader,
        device: str,
        binary_classification=False,
        class_weights=None,
):
    """Run model validation for one epoch and return predictions.

    Args:
        model: Loaded HuggingFace model
        val_dataloader: DataLoader for validation data
        device: Device to run on ('cuda' or 'cpu')
        binary_classification: Whether it's binary classification
        class_weights: Optional class weights for imbalanced data

    Returns:
        Tuple of (predicted_labels, prediction_probabilities)
    """
    model.eval()

    # Initialize empty arrays to store results
    all_preds = []
    all_probs = []

    with torch.no_grad():
        progress_bar = tqdm(val_dataloader, desc="Validating", leave=False)

        for batch in progress_bar:
            # Move batch to device
            input_ids = batch[0].to(device)
            attention_mask = batch[1].to(device)
            token_type_ids = batch[2].to(device)

            # Forward pass - key modification here
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                token_type_ids=token_type_ids
            )

            # Handle different output types
            if hasattr(outputs, 'logits'):
                logits = outputs.logits
            else:
                logits = outputs  # For models that return logits directly

            # Calculate probabilities
            if binary_classification:
                probs = torch.sigmoid(logits).cpu().numpy()
                preds = (probs > 0.5).astype(int).squeeze()
            else:
                probs = torch.softmax(logits, dim=1).cpu().numpy()
                preds = np.argmax(probs, axis=1)

            # Store results
            all_preds.append(preds)
            all_probs.append(probs)

    # Concatenate all batch results
    final_preds = np.concatenate(all_preds) if len(all_preds[0].shape) > 0 else np.hstack(all_preds)
    final_probs = np.concatenate(all_probs)

    return final_preds, final_probs
