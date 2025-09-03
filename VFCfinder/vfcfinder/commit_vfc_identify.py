#!/usr/bin/env python3
"""
Commit VFC识别工具

执行用例:
    # 指定输入和输出文件
    python commit_vfc_identify.py input_commits.json ranked_results.json
    python commit_vfc_identify.py input_commits.csv ranked_results.csv

    # 如果没有输入文件，将从Gitee获取OpenHarmony仓库数据
    python commit_vfc_identify.py
"""

import os
# 设置HF镜像端点
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
print("当前Endpoint:", os.environ.get("HF_ENDPOINT"))
import argparse
import json
import pandas as pd
import numpy as np
from pathlib import Path
import vfc_ranker
from utils import git_helper
from sklearn.utils import resample
class CommitRanker:
    def __init__(self):
        self.access_token = os.environ.get('GITEE_TOKEN')
        self.org_name = "openharmony"
        self.clone_path = "./../test_clone_repo/"
        self.repo_url = "https://gitee.com/openharmony/kernel_liteos_a"

    import pandas as pd
    import json
    import numpy as np
    from pathlib import Path

    def load_input_data(self,input_path: str, max_rows: int = None) -> pd.DataFrame:
        """
        统一加载JSON/CSV文件，确保输出DataFrame格式完全一致

        参数:
            input_path: 文件路径(.json/.csv)
            max_rows: 最大读取行数

        返回:
            标准化后的DataFrame (保证与JSON加载结构一致)

        特性:
            1. 自动处理嵌套JSON结构
            2. 智能类型推断（匹配JSON的自动类型检测）
            3. 统一缺失值标记为np.nan
            4. 列顺序标准化
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_path}")

        # 统一加载逻辑
        if input_path.suffix.lower() == '.json':
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            df = pd.json_normalize(data if isinstance(data, list) else [data])

        elif input_path.suffix.lower() == '.csv':
            # 首次探测类型
            sample_df = pd.read_csv(input_path, nrows=100)

            # 智能类型推断（匹配JSON行为）
            dtype = {}
            for col in sample_df.columns:
                if pd.api.types.is_numeric_dtype(sample_df[col]):
                    dtype[col] = 'float64'  # 统一数值类型
                elif pd.api.types.is_bool_dtype(sample_df[col]):
                    dtype[col] = 'bool'
                else:
                    dtype[col] = 'str'

            # 正式读取
            df = pd.read_csv(
                input_path,
                nrows=max_rows,
                dtype=dtype,
                true_values=['true', 'True'],
                false_values=['false', 'False'],
                keep_default_na=True,
                na_values=['', 'null', 'None', 'NA', 'N/A']
            )

            # 处理嵌套结构（CSV中存储的JSON字符串）
            for col in df.columns:
                if df[col].astype(str).str.startswith('{').any():
                    try:
                        df[col] = df[col].apply(lambda x: json.loads(x) if pd.notnull(x) else np.nan)
                        df = pd.concat([df.drop(col, axis=1), pd.json_normalize(df[col])], axis=1)
                    except:
                        pass
        else:
            raise ValueError(f"不支持的格式: {input_path.suffix}")

        # 后处理标准化
        df = df.convert_dtypes()  # 使用pandas最佳类型推断
        df.replace([None, 'null', 'NULL', ''], np.nan, inplace=True)


        # 确保列顺序稳定（按字母排序，可自定义）
        df = df.reindex(sorted(df.columns), axis=1)

        # df = df[df['partition'] == 'test']

        print(f"初始正样本数: {sum(df['label'] == '1')}/{len(df)}")
        print(f"初始负样本数: {sum(df['label'] == '0')}/{len(df)}")
        return df.head(max_rows) if max_rows is not None else df


    def safe_get_labels(self,df, label_col='label'):
        """安全提取标签列并标准化"""
        # 统一转为字符串并清理
        labels = (
            df[label_col]
            .astype(str)  # 强制转为字符串
            .str.strip()  # 去除首尾空格
            .str.lower()  # 统一小写
            .replace({
                'true': '1', 'false': '0',
                '1.0': '1', '0.0': '0',
                '': '0', 'nan': '0', 'none': '0'
            })
        )

        # 验证标签值
        valid_labels = {'0', '1'}
        invalid_labels = set(labels.unique()) - valid_labels

        if invalid_labels:
            raise ValueError(f"发现无效标签值: {invalid_labels}")

        return labels

    def fetch_from_gitee(self) -> pd.DataFrame:
        """从Gitee API获取仓库数据"""
        print("从Gitee获取仓库数据...")
        repos = git_helper.get_gitee_repos(self.org_name, self.access_token)
        print(f"共找到 {len(repos)} 个仓库")

        commits_diff = []
        for repo in repos:
            print(f"处理仓库: {repo}")
            # print("repo html_url:",repo['html_url'])
            print("repo url rstrip .git:",repo['html_url'].rstrip(".git"))
            diff = vfc_ranker.extract_diff(
                repo_url=repo['html_url'].rstrip(".git"),
                clone_path=self.clone_path,
                output_path="debug_commits_diff_raw.csv",
                git_token=self.access_token
            )
            if(diff.empty):
                print(f"仓库 {repo} 没有提交记录")
            else:
                commits_diff.append(diff)
        print(f"共找到 {len(commits_diff)} 条提交记录")

        if(len(commits_diff)==0):
            return pd.DataFrame()

        return pd.concat(commits_diff, ignore_index=True)

    def balance_by_undersampling(self, df):
        # 安全获取标签
        labels = self.safe_get_labels(df)

        # 分离数据
        df_majority = df[labels == '0']
        df_minority = df[labels == '1']

        # 检查样本量
        if len(df_minority) == 0:
            sample_labels = labels.value_counts().to_dict()
            raise ValueError(f"无正样本！当前标签分布: {sample_labels}")

        # 下采样多数类
        df_majority_down = df_majority.sample(
            n=len(df_minority),
            random_state=42,
            replace=False
        )

        return pd.concat([df_majority_down, df_minority])

    def process(self, input_path: str = None, output_path: str = "default_repo_list"):
        """主处理流程"""
        try:
            if input_path:
                # commits_diff = self.load_input_data(input_path, max_rows=20000)
                commits_diff = self.load_input_data(input_path)
                print(f"成功从 {input_path} 加载 {len(commits_diff)} 条记录")
            else:
                commits_diff = self.fetch_from_gitee()

            if(commits_diff.empty):
                print("今日没有检索到提交记录")
                return

            # 转换 labels 为 label (保持DataFrame结构)
            if hasattr(commits_diff, 'columns') and 'labels' in commits_diff.columns:
                commits_diff['label'] = commits_diff['labels']
                commits_diff.drop('labels', axis=1, inplace=True)
            elif isinstance(commits_diff, list):
                # 如果已经是列表，转换为DataFrame
                commits_diff = pd.DataFrame(commits_diff)
                if 'labels' in commits_diff.columns:
                    commits_diff['label'] = commits_diff['labels']

                    commits_diff.drop('labels', axis=1, inplace=True)


            # ===================  验证集用  =======================
            # 添加数据验证日志
            print(f"数据类型验证: {type(commits_diff)}")
            if hasattr(commits_diff, 'iloc'):
                print(f"首行类型: {type(commits_diff.iloc[0])}")
                print(f"首行内容: {commits_diff.iloc[0].to_dict()}")
            # print(f"列名列表: {commits_diff.columns.tolist()}")

            print("数据分布:")
            print(commits_diff['label'].value_counts())
            print("\n缺失值统计:")
            print(commits_diff.isnull().sum())
            # 下采样
            commits_diff = self.balance_by_undersampling(commits_diff)

            # 统计label为1和0的数量 - 正确方式
            label_counts = {'0': 0, '1': 0}
            if isinstance(commits_diff, pd.DataFrame):
                # 使用iterrows()正确遍历DataFrame
                for _, row in commits_diff.iterrows():
                    # 使用安全的列访问方式
                    label = str(row.get('label', '-1')) if hasattr(row, 'get') else '-1'
                    if label in ['0', '1']:
                        label_counts[label] += 1
            else:
                # 处理列表或其他类型
                for commit in commits_diff:
                    if isinstance(commit, dict):
                        label = str(commit.get('label', '-1'))
                    elif hasattr(commit, 'get'):
                        label = str(commit.get('label', '-1'))
                    else:
                        label = '-1'
                    if label in ['0', '1']:
                        label_counts[label] += 1

            print(f"Label统计结果 - 0: {label_counts['0']} 条, 1: {label_counts['1']} 条")
            # ===================  验证集用  =======================

            # 执行排名
            ranked_commits = vfc_ranker.rank2(
                return_results=True,
                output_path=output_path,
                commit_diff=commits_diff
            )


            print(f"处理完成，结果已保存到: {output_path}")
            return ranked_commits

        except Exception as e:
            print(f"处理失败: {str(e)}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Commit VFC识别工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python commit_vfc_identify.py -i input.json -o output.json\n"
               "  python commit_vfc_identify.py -i input.csv -o output.csv\n"
               "  python commit_vfc_identify.py (从Gitee获取数据)"
    )

    # 使用 -i/--input 替代位置参数
    parser.add_argument(
        '-i', '--input',
        dest='input_file',
        help='输入文件路径（JSON/CSV），如未提供则从Gitee获取数据'
    )

    # 使用 -o/--output 替代位置参数
    parser.add_argument(
        '-o', '--output',
        dest='output_file',
        default='default_repo_list',
        help='输出文件路径（默认: default_repo_list）'
    )
    args = parser.parse_args()

    ranker = CommitRanker()
    ranker.process(args.input_file, args.output_file)

if __name__ == "__main__":
    main()