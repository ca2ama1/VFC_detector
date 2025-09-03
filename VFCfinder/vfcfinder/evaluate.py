import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_curve, auc, precision_recall_curve,
    classification_report
)
from sklearn.calibration import calibration_curve

# 设置中文字体和样式
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")


def calculate_model_metrics(df, label_col='labels', prob_col='vfc_prob', threshold=0.5):
    """
    计算模型预测的各项指标
    """
    # 确保数据格式正确
    df = df.copy()
    df[label_col] = df[label_col].astype(int)
    df[prob_col] = df[prob_col].astype(float)

    # 根据阈值生成预测标签
    y_true = df[label_col]
    y_pred_proba = df[prob_col]
    y_pred = (y_pred_proba >= threshold).astype(int)

    # 计算各项指标
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    # 计算误报率（False Positive Rate）
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    # 计算特异性（Specificity）
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0

    # 计算ROC曲线和AUC
    fpr_roc, tpr_roc, _ = roc_curve(y_true, y_pred_proba)
    roc_auc = auc(fpr_roc, tpr_roc)

    # 计算PR曲线和AUC
    precision_pr, recall_pr, _ = precision_recall_curve(y_true, y_pred_proba)
    pr_auc = auc(recall_pr, precision_pr)

    # 计算校准曲线
    prob_true, prob_pred = calibration_curve(y_true, y_pred_proba, n_bins=10)

    metrics = {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'false_positive_rate': fpr,
        'specificity': specificity,
        'roc_auc': roc_auc,
        'pr_auc': pr_auc,
        'confusion_matrix': confusion_matrix(y_true, y_pred),
        'classification_report': classification_report(y_true, y_pred),
        'roc_curve': (fpr_roc, tpr_roc),
        'pr_curve': (precision_pr, recall_pr),
        'calibration_curve': (prob_true, prob_pred)
    }

    return metrics, y_true, y_pred, y_pred_proba


def plot_confusion_matrix(cm, save_path='confusion_matrix.png'):
    """绘制混淆矩阵"""
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=['Negative', 'Positive'],
                yticklabels=['Negative', 'Positive'])
    plt.title('Confusion Matrix')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"混淆矩阵已保存: {save_path}")


def plot_roc_curve(fpr, tpr, roc_auc, save_path='roc_curve.png'):
    """绘制ROC曲线"""
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver Operating Characteristic (ROC) Curve')
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"ROC曲线已保存: {save_path}")


def plot_pr_curve(precision, recall, pr_auc, save_path='pr_curve.png'):
    """绘制PR曲线"""
    plt.figure(figsize=(8, 6))
    plt.plot(recall, precision, color='blue', lw=2, label=f'PR curve (AUC = {pr_auc:.3f})')
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Curve')
    plt.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"PR曲线已保存: {save_path}")


def plot_calibration_curve(prob_true, prob_pred, save_path='calibration_curve.png'):
    """绘制校准曲线"""
    plt.figure(figsize=(8, 6))
    plt.plot(prob_pred, prob_true, 's-', label='Model')
    plt.plot([0, 1], [0, 1], '--', color='gray', label='Perfectly calibrated')
    plt.xlabel('Mean predicted probability')
    plt.ylabel('Fraction of positives')
    plt.title('Calibration Curve')
    plt.legend()
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"校准曲线已保存: {save_path}")


def plot_metrics_bar(metrics, save_path='metrics_bar.png'):
    """绘制指标条形图"""
    metrics_to_plot = {
        'Accuracy': metrics['accuracy'],
        'Precision': metrics['precision'],
        'Recall': metrics['recall'],
        'F1-Score': metrics['f1_score'],
        'Specificity': metrics['specificity']
    }

    plt.figure(figsize=(10, 6))
    bars = plt.bar(metrics_to_plot.keys(), metrics_to_plot.values(),
                   color=['skyblue', 'lightgreen', 'lightcoral', 'gold', 'plum'])
    plt.title('Model Performance Metrics')
    plt.ylabel('Score')
    plt.ylim(0, 1)

    # 在条形上添加数值标签
    for bar, value in zip(bars, metrics_to_plot.values()):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                 f'{value:.3f}', ha='center', va='bottom')

    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"指标条形图已保存: {save_path}")


def save_metrics_to_csv(metrics, file_suffix=''):
    """保存指标到CSV文件"""
    metrics_df = pd.DataFrame({
        'Metric': ['Accuracy', 'Precision', 'Recall', 'F1-Score',
                   'Specificity', 'False Positive Rate', 'ROC AUC', 'PR AUC'],
        'Value': [metrics['accuracy'], metrics['precision'], metrics['recall'],
                  metrics['f1_score'], metrics['specificity'], metrics['false_positive_rate'],
                  metrics['roc_auc'], metrics['pr_auc']]
    })
    save_path = 'model_metrics_'+file_suffix+'.csv'
    metrics_df.to_csv(save_path, index=False)
    print(f"指标数据已保存: {save_path}")


def main(csv_file_path, label_col='labels', prob_col='vfc_prob', threshold=0.5,file_suffix=''):
    """
    主函数：读取CSV文件，计算指标并绘制图表
    """
    # 读取数据
    df = pd.read_csv(csv_file_path)
    print(f"数据读取完成，共 {len(df)} 条记录")
    print(f"正样本数量: {df[label_col].sum()}")
    print(f"负样本数量: {len(df) - df[label_col].sum()}")

    # 计算指标
    metrics, y_true, y_pred, y_pred_proba = calculate_model_metrics(
        df, label_col, prob_col, threshold
    )

    # 打印指标
    print("\n=== 模型性能指标 ===")
    print(f"准确率 (Accuracy): {metrics['accuracy']:.4f}")
    print(f"精确率 (Precision): {metrics['precision']:.4f}")
    print(f"召回率 (Recall): {metrics['recall']:.4f}")
    print(f"F1分数 (F1-Score): {metrics['f1_score']:.4f}")
    print(f"特异性 (Specificity): {metrics['specificity']:.4f}")
    print(f"误报率 (False Positive Rate): {metrics['false_positive_rate']:.4f}")
    print(f"ROC AUC: {metrics['roc_auc']:.4f}")
    print(f"PR AUC: {metrics['pr_auc']:.4f}")

    print("\n=== 混淆矩阵 ===")
    print(metrics['confusion_matrix'])

    print("\n=== 分类报告 ===")
    print(metrics['classification_report'])

    # # 绘制并保存图表
    # plot_confusion_matrix(metrics['confusion_matrix'])
    # plot_roc_curve(*metrics['roc_curve'], metrics['roc_auc'])
    # plot_pr_curve(*metrics['pr_curve'], metrics['pr_auc'])
    # plot_calibration_curve(*metrics['calibration_curve'])
    # plot_metrics_bar(metrics)

    # 保存指标到CSV
    save_metrics_to_csv(metrics,file_suffix)

    return metrics


# 使用示例
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='模型性能评估工具')
    parser.add_argument('--file', '-f', type=str, required=True,
                       help='CSV文件路径')
    parser.add_argument('--suffix', '-s', type=str, required=True,
                       help='保存的文件后缀')
    # 解析参数
    args = parser.parse_args()
    # 替换为你的CSV文件路径
    csv_file_dir = "VFCfinder/results/"  # 修改为你的文件路径

    # 运行分析
    results = main(csv_file_dir+args.file, label_col='label', prob_col='vfc_prob', threshold=0.5,file_suffix=args.suffix)
