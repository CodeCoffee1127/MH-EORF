"""
lead_time.py

计算提前量指标。

指标:
- Warning Coverage: 正例中被预警的比例
- Mean Lead Time: 平均提前步数
- Median Lead Time: 中位提前步数
- Late Warning Rate: 迟到预警率（预警步数 >= 2）
- Miss Rate: 漏报率
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from sl_rdaf.data.schema import SAMPLE_ID_COL, STEP_T_COL


def compute_lead_time_metrics(
    heldout_df: pd.DataFrame,
    y_hat: np.ndarray,
    Q_tilde: np.ndarray,
    y_cum: np.ndarray,
    valid_mask_cum: np.ndarray,
    thresholds: Dict,
) -> Dict:
    """
    计算提前量指标。

    注意: 如果标签信息不足以可靠计算提前量，返回 None 并记录原因。

    Args:
        heldout_df: heldout DataFrame
        y_hat: [N, 3]，预警预测
        Q_tilde: [N, 3]，校准后累积风险
        y_cum: [N, 3]，累积风险标签
        valid_mask_cum: [N, 3]，有效掩码
        thresholds: {theta_1, theta_2, theta_3}

    Returns:
        提前量指标字典
    """
    # 检查是否有足够的正例
    lead_time_results = {}

    for h_idx, h in enumerate([1, 2, 3]):
        mask = valid_mask_cum[:, h_idx] == 1
        y_valid = y_cum[mask, h_idx]
        y_hat_valid = y_hat[mask, h_idx]

        # 移除 NaN
        valid_idx = ~np.isnan(y_valid)
        y_valid = y_valid[valid_idx]
        y_hat_valid = y_hat_valid[valid_idx]

        n_positive = int(np.nansum(y_valid))
        n_total = int(valid_idx.sum())

        if n_positive == 0:
            lead_time_results[f"h{h}"] = {
                "Warning_Coverage": None,
                "Mean_Lead_Time": None,
                "Median_Lead_Time": None,
                "Late_Warning_Rate": None,
                "Miss_Rate": 1.0,
                "note": "No positive labels in this horizon",
            }
            continue

        # Warning Coverage = TP / (TP + FN) = Recall
        tp = int(((y_hat_valid == 1) & (y_valid == 1)).sum())
        fn = int(((y_hat_valid == 0) & (y_valid == 1)).sum())

        warning_coverage = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        miss_rate = fn / (tp + fn) if (tp + fn) > 0 else 1.0

        # 提前量计算需要知道首次预警步数和首次退化步数
        # 由于当前数据结构限制，这里简化处理
        # 实际应该追踪每个样本的预警时间线

        lead_time_results[f"h{h}"] = {
            "Warning_Coverage": float(warning_coverage),
            "Mean_Lead_Time": None,  # 需要更详细的时序信息
            "Median_Lead_Time": None,  # 需要更详细的时序信息
            "Late_Warning_Rate": None,  # 需要更详细的时序信息
            "Miss_Rate": float(miss_rate),
            "n_positive": n_positive,
            "n_total": n_total,
            "note": "Lead-time metrics could not be computed reliably because the current data structure does not track first-warning-step and first-degradation-step for each sample.",
        }

    return lead_time_results


def print_lead_time_summary(lead_time_results: Dict):
    """
    打印提前量指标摘要。

    Args:
        lead_time_results: compute_lead_time_metrics 的返回结果
    """
    print("\n  提前量指标:")
    print("  " + "-" * 70)

    for h in [1, 2, 3]:
        key = f"h{h}"
        lt = lead_time_results[key]

        print(f"\n  h={h}:")
        print(f"    Warning Coverage: {lt['Warning_Coverage']:.4f}" if lt['Warning_Coverage'] is not None else "    Warning Coverage: N/A")
        print(f"    Miss Rate: {lt['Miss_Rate']:.4f}")

        if lt.get('note'):
            print(f"    Note: {lt['note']}")

    print("\n  " + "-" * 70)
