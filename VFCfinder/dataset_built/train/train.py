#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
代码漏洞检测模型训练脚本

功能描述：
1. 使用CodeBERT模型进行代码漏洞检测的二分类任务
2. 支持单机多卡分布式训练
3. 包含完整的数据加载、预处理、训练和评估流程

主要特点：
- 基于HuggingFace Transformers库
- 支持分布式数据并行训练(DDP)
- 自动混合精度训练(FP16)
- 丰富的训练参数配置
- 完善的错误处理和日志记录

数据集要求：
- 训练数据应为JSON格式，包含"input"和"label"字段
- 正负样本分别存放在不同文件中

使用方法：
1. 配置下方路径参数
2. 单卡训练：python script.py
3. 多卡训练：torchrun --nproc_per_node=N script.py

CUDA_VISIBLE_DEVICES=0 python train.py


输出结果：
- 训练日志和TensorBoard记录
- 保存的最佳模型(checkpoints)
- 评估结果
"""

import os
import torch

# ====================== 环境配置 ======================
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # 使用HF镜像
os.environ['NCCL_DEBUG'] = 'INFO'  # NCCL调试信息

#根据网络接口有所变化
os.environ['NCCL_SOCKET_IFNAME'] = 'eno33'  # 指定网络接口
os.environ['NCCL_IB_DISABLE'] = '1'  # 禁用InfiniBand
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'  # 同步CUDA操作
os.environ['TOKENIZERS_PARALLELISM'] = 'false'  # 禁用tokenizer并行

# ====================== 路径配置 ======================
# 训练数据路径
TRAIN_VUL_DATASET = "train_dataset/train_vul_dataset.json"  # 漏洞样本数据
TRAIN_NONVUL_DATASET = "train_dataset/train_nonvul_dataset.json"  # 非漏洞样本数据
# VALID_VUL_DATASET = "valid_vul_dataset.json"                  # 验证集(可选)
# VALID_NONVUL_DATASET = "valid_nonvul_dataset.json"           # 验证集(可选)

# 模型保存路径
MODEL_SAVE_DIR = "./vfc_finetuned_0902_codebert/best_model"  # 最终模型保存路径
TEMP_DATASET_DIR = "./temp_dataset"  # 临时数据集路径

# 日志和输出目录
OUTPUT_DIR = "./vfc_finetuned"  # 训练输出目录
LOGGING_DIR = "./logs"  # TensorBoard日志目录

# ====================== 模型配置 ======================
MODEL_NAME = "microsoft/codebert-base"  # 基础模型
# MODEL_NAME = "microsoft/codebert-large"  # 大模型选项
# MODEL_NAME = "microsoft/unixcoder-base"  # UniXcoder选项
# MODEL_NAME = "microsoft/graphcodebert-base"  # GraphCodeBERT选项

# ====================== 训练参数 ======================
BATCH_SIZE = 32  # 每设备训练批次大小
EVAL_BATCH_SIZE = 8  # 每设备评估批次大小
GRADIENT_ACCUMULATION_STEPS = 2  # 梯度累积步数
EPOCHS = 50  # 训练轮数
LEARNING_RATE = 5e-5  # 学习率
WEIGHT_DECAY = 0.05  # 权重衰减
WARMUP_RATIO = 0.95  # warmup比例
MAX_SEQ_LENGTH = 512  # 最大序列长度


# ====================== 辅助函数 ======================
def setup(rank, world_size):
    """初始化分布式训练环境"""
    torch.cuda.set_device(rank)
    dist.init_process_group(
        backend="nccl",
        init_method="env://",
        rank=rank,
        world_size=world_size,
        timeout=datetime.timedelta(seconds=60)
    )


def cleanup():
    """清理分布式训练环境"""
    if dist.is_initialized():
        dist.destroy_process_group()


def tokenize_function(examples):
    """数据集tokenize处理"""
    tokenized = tokenizer(
        examples["input"],
        padding="max_length",
        truncation=True,
        max_length=MAX_SEQ_LENGTH,
        return_tensors="pt"
    )
    return {
        "input_ids": tokenized["input_ids"],
        "attention_mask": tokenized["attention_mask"],
        "labels": torch.tensor(examples["labels"], dtype=torch.long)
    }


# ====================== 主函数 ======================
def main():
    # 初始化默认值
    rank = 0
    world_size = 1

    try:
        # 检查是否是分布式环境
        if 'LOCAL_RANK' in os.environ:
            rank = int(os.environ['LOCAL_RANK'])
            world_size = int(os.environ['WORLD_SIZE'])
            setup(rank, world_size)
            print(f"Initialized process group: rank {rank}, world size {world_size}")
        else:
            print("Running in non-distributed mode")

        # 1. 数据加载（主进程负责）
        if rank == 0 or not dist.is_initialized():
            print("Loading datasets...")
            vul_dataset = load_dataset('json', data_files=TRAIN_VUL_DATASET)['train']
            nonvul_dataset = load_dataset('json', data_files=TRAIN_NONVUL_DATASET)['train']
            full_dataset = concatenate_datasets([vul_dataset, nonvul_dataset])
            full_dataset = full_dataset.rename_column("label", "labels")
            full_dataset.save_to_disk(TEMP_DATASET_DIR)

        if dist.is_initialized():
            dist.barrier()  # 同步点

        # 所有进程加载数据
        dataset = Dataset.load_from_disk(TEMP_DATASET_DIR).train_test_split(test_size=0.2, seed=42)

        # 2. 模型初始化
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = RobertaForSequenceClassification.from_pretrained(
            MODEL_NAME,
            num_labels=2,
        ).to(rank)

        # 模型配置调整
        model.config.hidden_dropout_prob = 0.2
        model.config.attention_probs_dropout_prob = 0.1

        if dist.is_initialized():
            model = DDP(model, device_ids=[rank], output_device=rank)

        # 3. 数据预处理
        tokenized_datasets = dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=["input"],
            batch_size=16
        )
        tokenized_datasets.set_format(
            type="torch",
            columns=["input_ids", "attention_mask", "labels"]
        )

        # 4. 训练配置
        training_args = TrainingArguments(
            output_dir=OUTPUT_DIR,
            evaluation_strategy="epoch",
            per_device_train_batch_size=BATCH_SIZE,
            per_device_eval_batch_size=EVAL_BATCH_SIZE,
            gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
            num_train_epochs=EPOCHS,
            learning_rate=LEARNING_RATE,
            weight_decay=WEIGHT_DECAY,
            warmup_ratio=WARMUP_RATIO,
            warmup_steps=500,
            lr_scheduler_type="cosine",
            fp16=False,
            dataloader_num_workers=0,
            max_grad_norm=0.5,
            adam_epsilon=1e-8,
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            save_total_limit=3,
            logging_dir=LOGGING_DIR,
            logging_steps=10,
            report_to="tensorboard",
            gradient_checkpointing=False,
            local_rank=rank,
            ddp_find_unused_parameters=False,
            remove_unused_columns=False,
            label_names=["labels"],
            dataloader_pin_memory=False,
            optim="adamw_torch"
        )

        # 5. 创建Trainer
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_datasets["train"],
            eval_dataset=tokenized_datasets["test"],
            data_collator=default_data_collator,
            tokenizer=tokenizer
        )

        # 6. 训练
        if rank == 0:
            print("\n===== Training Starting =====")
            print("首批次数据示例:", next(iter(trainer.get_train_dataloader())))
        trainer.train()

        # 7. 保存模型
        if rank == 0:
            print("\n===== Saving Best Model =====")
            trainer.save_model(MODEL_SAVE_DIR)

            # 检查必要文件
            required_files = [
                "config.json",
                "pytorch_model.bin",
                "training_args.bin",
                "tokenizer_config.json",
                "special_tokens_map.json"
            ]
            missing = [f for f in required_files
                       if not os.path.exists(f"{MODEL_SAVE_DIR}/{f}")]
            if missing:
                print(f"警告：缺失文件 {missing}")

    except Exception as e:
        print(f"[Rank {rank}] Error: {str(e)}", flush=True)
        raise
    finally:
        if dist.is_initialized():
            cleanup()


if __name__ == "__main__":
    import datetime
    import torch.distributed as dist
    from torch.nn.parallel import DistributedDataParallel as DDP
    from datasets import load_dataset, Dataset, concatenate_datasets
    from transformers import (
        RobertaForSequenceClassification,
        TrainingArguments,
        Trainer,
        AutoTokenizer,
        default_data_collator
    )

    main()

# import os
# import torch
#
# os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
# import datetime
# import torch.distributed as dist
# from torch.nn.parallel import DistributedDataParallel as DDP
# from datasets import load_dataset, Dataset, concatenate_datasets
# from transformers import (
#     RobertaForSequenceClassification,
#     TrainingArguments,
#     Trainer,
#     AutoTokenizer,
#     default_data_collator
# )
#
# # 环境配置
# os.environ['NCCL_DEBUG'] = 'INFO'
# os.environ['NCCL_SOCKET_IFNAME'] = 'eno33'
# os.environ['NCCL_IB_DISABLE'] = '1'
# os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
# os.environ['TOKENIZERS_PARALLELISM'] = 'false'
#
# def setup(rank, world_size):
#     torch.cuda.set_device(rank)
#     dist.init_process_group(
#         backend="nccl",
#         init_method="env://",
#         rank=rank,
#         world_size=world_size,
#         timeout=datetime.timedelta(seconds=60)
#     )
#
#
# def cleanup():
#     if dist.is_initialized():
#         dist.destroy_process_group()
#
#
# def main():
#     # 初始化默认值
#     rank = 0
#     world_size = 1
#
#     try:
#         # 检查是否是分布式环境
#         if 'LOCAL_RANK' in os.environ:
#             rank = int(os.environ['LOCAL_RANK'])
#             world_size = int(os.environ['WORLD_SIZE'])
#             setup(rank, world_size)
#             print(f"Initialized process group: rank {rank}, world size {world_size}")
#         else:
#             print("Running in non-distributed mode")
#
#         # 1. 数据加载（主进程负责）
#         if rank == 0 or not dist.is_initialized():
#             print("Loading datasets...")
#             vul_dataset = load_dataset('json', data_files="train_dataset/train_vul_dataset.json")['train']
#             nonvul_dataset = load_dataset('json', data_files="train_dataset/train_nonvul_dataset.json")['train']
#             # vul_dataset = load_dataset('json', data_files="valid_vul_dataset.json")['train']
#             # nonvul_dataset = load_dataset('json', data_files="valid_nonvul_dataset.json")['train']
#             full_dataset = concatenate_datasets([vul_dataset, nonvul_dataset])
#             full_dataset = full_dataset.rename_column("label", "labels")  # 统一字段名
#             full_dataset.save_to_disk("./temp_dataset")
#
#         if dist.is_initialized():
#             dist.barrier()  # 同步点
#
#         # 所有进程加载数据
#         dataset = Dataset.load_from_disk("./temp_dataset").train_test_split(test_size=0.2, seed=42)
#
#         # 2. 模型初始化
#         tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
#         model = RobertaForSequenceClassification.from_pretrained(
#             # "tdunlap607/vfc-identification",
#             "microsoft/codebert-base",
#             # "microsoft/codebert-large",
#             num_labels=2,
#             # torch_dtype=torch.float16
#         ).to(rank)
#
#         # 选项1：Microsoft CodeBERT（基础版）
#         # tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
#         # model = AutoModelForSequenceClassification.from_pretrained(
#         #     "microsoft/codebert-base",
#         #     num_labels=2
#         # ).to(rank)
#
#         # # 选项2：更强大的CodeBERT-large
#         # tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-large")
#         # model = AutoModelForSequenceClassification.from_pretrained(
#         #     "microsoft/codebert-large",
#         #     num_labels=2
#         # ).to(device)
#         #
#         # # 选项3：UniXcoder（专门用于代码理解）
#         # tokenizer = AutoTokenizer.from_pretrained("microsoft/unixcoder-base")
#         # model = AutoModelForSequenceClassification.from_pretrained(
#         #     "microsoft/unixcoder-base",
#         #     num_labels=2
#         # ).to(device)
#         #
#         # # 选项4：GraphCodeBERT（考虑代码结构）
#         # tokenizer = AutoTokenizer.from_pretrained("microsoft/graphcodebert-base")
#         # model = AutoModelForSequenceClassification.from_pretrained(
#         #     "microsoft/graphcodebert-base",
#         #     num_labels=2
#         # ).to(device)
#         model.config.hidden_dropout_prob = 0.2  # 隐藏层Dropout
#         model.config.attention_probs_dropout_prob = 0.1  # 注意力Dropout
#
#         if dist.is_initialized():
#             model = DDP(model, device_ids=[rank], output_device=rank)
#
#         # 3. 数据预处理
#         def tokenize_function(examples):
#             tokenized = tokenizer(
#                 examples["input"],
#                 padding="max_length",
#                 truncation=True,
#                 max_length=512,
#                 return_tensors="pt"
#             )
#             return {
#                 "input_ids": tokenized["input_ids"],
#                 "attention_mask": tokenized["attention_mask"],
#                 "labels": torch.tensor(examples["labels"], dtype=torch.long)
#             }
#
#         tokenized_datasets = dataset.map(
#             tokenize_function,
#             batched=True,
#             remove_columns=["input"],
#             batch_size=16
#         )
#
#         # 强制设置格式
#         tokenized_datasets.set_format(
#             type="torch",
#             columns=["input_ids", "attention_mask", "labels"]
#         )
#
#         # 4. 训练配置
#         training_args = TrainingArguments(
#             output_dir="./vfc_finetuned",
#             evaluation_strategy="epoch",
#             per_device_train_batch_size=32,
#             per_device_eval_batch_size=8,
#             gradient_accumulation_steps=2,
#             num_train_epochs=50,
#             learning_rate=5e-5,
#             weight_decay=0.05,
#             warmup_ratio=0.95,  # 添加10%的训练步数作为warmup
#             warmup_steps=500,  # 明确warmup步数
#             lr_scheduler_type="cosine",  # 改用cosine衰减
#             fp16=False,
#             dataloader_num_workers=0,
#             max_grad_norm=0.5,  # 梯度裁剪
#             adam_epsilon=1e-8,  # 优化器参数
#             save_strategy="epoch",
#             load_best_model_at_end=True,  # 训练结束时加载最佳模型
#             metric_for_best_model="eval_loss",  # 根据验证损失选择最佳模型
#             greater_is_better=False,  # 损失越小越好
#             save_total_limit=3,  # 最多保留3个checkpoint
#             logging_dir="./logs",
#             logging_steps=10,
#             report_to="tensorboard",
#             gradient_checkpointing=False,
#             local_rank=rank,
#             ddp_find_unused_parameters=False,
#             remove_unused_columns=False,
#             label_names=["labels"],
#             dataloader_pin_memory=False,
#             optim="adamw_torch"  # 使用PyTorch的AdamW实现
#         )
#
#         # 5. 创建Trainer
#         trainer = Trainer(
#             model=model,
#             args=training_args,
#             train_dataset=tokenized_datasets["train"],
#             eval_dataset=tokenized_datasets["test"],
#             data_collator=default_data_collator,
#             tokenizer=tokenizer
#         )
#
#         # 6. 训练
#         if rank == 0:
#             print("\n===== Training Starting =====")
#             print("首批次数据示例:", next(iter(trainer.get_train_dataloader())))
#         trainer.train()
#
#         # 在训练结束后添加（main函数末尾）
#         if rank == 0:
#             print("\n===== Saving Best Model =====")
#             # 保存完整模型包
#             trainer.save_model("./vfc_finetuned_0902_codebert/best_model")
#
#             # 确保所有必要文件都被保存
#             required_files = [
#                 "config.json",
#                 "pytorch_model.bin",
#                 "training_args.bin",
#                 "tokenizer_config.json",
#                 "special_tokens_map.json"
#             ]
#             missing = [f for f in required_files
#                        if not os.path.exists(f"./vfc_finetuned_0902_codebert/best_model/{f}")]
#             if missing:
#                 print(f"警告：缺失文件 {missing}")
#
#     except Exception as e:
#         print(f"[Rank {rank}] Error: {str(e)}", flush=True)
#         raise
#     finally:
#         if dist.is_initialized():
#             cleanup()
#
#
# if __name__ == "__main__":
#     main()
