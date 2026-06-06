"""
horizon_metrics.py

按 horizon 计算评估指标。

指标:
- AUROC
- AUPRC
- Precision
- Recall
- F1
- Alert Rate
- Brier Score
"""

import numpy as np
from typing import Dict
from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score, f1_score


def compute_horizon_metrics(
    Q_tilde: np.ndarray,
    y_hat: np.ndarray,
    y_cum: np.ndarray,
    valid_mask_cum: np.ndarray,
) -> Dict:
    """
    按 horizon 计算指标。

    Args:
        Q_tilde: [N, 3]，校准后累积风险
        y_hat: [N, 3]，预警预测
        y_cum: [N, 3]，累积风险标签
        valid_mask_cum: [N, 3]，有效掩码

    Returns:
        指标字典
    """
    metrics = {}

    for h_idx, h in enumerate([1, 2, 3]):
        mask = valid_mask_cum[:, h_idx] == 1
        Q_valid = Q_tilde[mask, h_idx]  # 只取当前 horizon
        y_hat_valid = y_hat[mask, h_idx]
        y_valid = y_cum[mask, h_idx]

        # 移除 NaN
        valid_idx = ~np.isnan(y_valid) & ~np.isnan(Q_valid)
        Q_valid = Q_valid[valid_idx]
        y_hat_valid = y_hat_valid[valid_idx]
        y_valid = y_valid[valid_idx]

        n_valid = int(valid_idx.sum())
        n_positive = int(y_valid.sum())

        # AUROC
        if len(np.unique(y_valid)) > 1:
            auroc = roc_auc_score(y_valid, Q_valid)
        else:
            auroc = np.nan

        # AUPRC
        if n_positive > 0:
            auprc = average_precision_score(y_valid, Q_valid)
        else:
            auprc = np.nan

        # Precision, Recall, F1
        precision = precision_score(y_valid, y_hat_valid, zero_division=0)
        recall = recall_score(y_valid, y_hat_valid, zero_division=0)
        f1 = f1_score(y_valid, y_hat_valid, zero_division=0)

        # Alert Rate
        alert_rate = y_hat_valid.mean()

        # Brier Score
        brier_score = np.mean((Q_valid - y_valid) ** 2)

        metrics[f"h{h}"] = {
            "n_valid": n_valid,
            "n_positive": n_positive,
            "positive_rate": float(n_positive / n_valid) if n_valid > 0 else 0.0,
            "AUROC": float(auroc) if not np.isnan(auroc) else None,
            "AUPRC": float(auprc) if not np.isnan(auprc) else None,
            "Precision": float(precision),
            "Recall": float(recall),
            "F1": float(f1),
            "Alert_Rate": float(alert_rate),
            "Brier_Score": float(brier_score),
        }

    return metrics


def print_metrics_summary(metrics: Dict):
    """
    打印指标摘要。

    Args:
        metrics: compute_horizon_metrics 的返回结果
    """
    print("\n  Heldout 评估指标:")
    print("  " + "-" * 70)
    print(f"  {'Horizon':<10} {'AUROC':<10} {'AUPRC':<10} {'F1':<10} {'Alert Rate':<12} {'Brier':<10}")
    print("  " + "-" * 70)

    for h in [1, 2, 3]:
        key = f"h{h}"
        m = metrics[key]
        auroc_str = f"{m['AUROC']:.4f}" if m['AUROC'] is not None else "N/A"
        auprc_str = f"{m['AUPRC']:.4f}" if m['AUPRC'] is not None else "N/A"
        print(f"  h={h:<8} {auroc_str:<10} {auprc_str:<10} {m['F1']:<10.4f} {m['Alert_Rate']:<12.4f} {m['Brier_Score']:<10.4f}")

    print("  " + "-" * 70)
