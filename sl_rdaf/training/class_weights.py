"""
class_weights.py

从 train-dev 计算类别权重。

规则:
- 只在 train-dev 上计算正例率
- h=1, h=2, h=3 的累积风险正例数/负例数
- k=1, k=2, k=3 的 hazard 正例数/负例数
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict
from sl_rdaf.data.schema import (
    SAMPLE_ID_COL,
    Y_I_T_H1, Y_I_T_H2, Y_I_T_H3,
    Y_HAZ_I_T_K1, Y_HAZ_I_T_K2, Y_HAZ_I_T_K3,
    VALID_H1, VALID_H2, VALID_H3,
    VALID_HAZ_K1, VALID_HAZ_K2, VALID_HAZ_K3,
)

OUTPUT_DIR = Path("D:/SL-RDAF/outputs/training")


def compute_class_weights(train_df: pd.DataFrame) -> Dict:
    """
    从 train-dev 计算类别权重。

    Args:
        train_df: train-dev 的 DataFrame

    Returns:
        包含正例数、负例数、正例率的字典
    """
    results = {
        "source": "train-dev only",
        "n_samples": int(train_df[SAMPLE_ID_COL].nunique()),
        "n_rows": int(len(train_df)),
    }

    # 累积风险标签 h=1,2,3
    y_cols_h = [Y_I_T_H1, Y_I_T_H2, Y_I_T_H3]
    valid_cols_h = [VALID_H1, VALID_H2, VALID_H3]
    h_labels = ["h1", "h2", "h3"]

    for y_col, valid_col, h_label in zip(y_cols_h, valid_cols_h, h_labels):
        if y_col in train_df.columns and valid_col in train_df.columns:
            # 只统计有效行
            mask = train_df[valid_col] == 1
            n_valid = int(mask.sum())
            n_positive = int(((train_df[y_col] == 1) & mask).sum())
            n_negative = int(n_valid - n_positive)
            positive_rate = n_positive / n_valid if n_valid > 0 else 0.0

            results[f"cumulative_risk_{h_label}"] = {
                "n_valid": n_valid,
                "n_positive": n_positive,
                "n_negative": n_negative,
                "positive_rate": float(positive_rate),
            }

    # Hazard 标签 k=1,2,3
    y_cols_k = [Y_HAZ_I_T_K1, Y_HAZ_I_T_K2, Y_HAZ_I_T_K3]
    valid_cols_k = [VALID_HAZ_K1, VALID_HAZ_K2, VALID_HAZ_K3]
    k_labels = ["k1", "k2", "k3"]

    for y_col, valid_col, k_label in zip(y_cols_k, valid_cols_k, k_labels):
        if y_col in train_df.columns and valid_col in train_df.columns:
            # 只统计有效行
            mask = train_df[valid_col] == 1
            n_valid = int(mask.sum())
            n_positive = int(((train_df[y_col] == 1) & mask).sum())
            n_negative = int(n_valid - n_positive)
            positive_rate = n_positive / n_valid if n_valid > 0 else 0.0

            results[f"hazard_{k_label}"] = {
                "n_valid": n_valid,
                "n_positive": n_positive,
                "n_negative": n_negative,
                "positive_rate": float(positive_rate),
            }

    # 计算类别权重（用于 loss）
    # 使用 inverse frequency: weight = n_negative / n_positive
    # 如果某类正例数为0，weight=1.0
    class_weights = {}
    for h_label in h_labels:
        key = f"cumulative_risk_{h_label}"
        if key in results:
            n_pos = results[key]["n_positive"]
            n_neg = results[key]["n_negative"]
            if n_pos > 0:
                class_weights[h_label] = float(n_neg / n_pos)
            else:
                class_weights[h_label] = 1.0

    results["class_weights_for_loss"] = class_weights

    # 保存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "class_weights_train_dev.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return results


def print_class_weights_summary(results: Dict):
    """
    打印类别权重摘要。

    Args:
        results: compute_class_weights 的返回结果
    """
    print("\n  类别权重统计 (train-dev):")
    print("  " + "-" * 60)

    # 累积风险
    for h_label in ["h1", "h2", "h3"]:
        key = f"cumulative_risk_{h_label}"
        if key in results:
            stats = results[key]
            print(f"  {h_label}: 有效={stats['n_valid']}, "
                  f"正例={stats['n_positive']}, "
                  f"负例={stats['n_negative']}, "
                  f"正例率={stats['positive_rate']:.4f}")

    print()

    # Hazard
    for k_label in ["k1", "k2", "k3"]:
        key = f"hazard_{k_label}"
        if key in results:
            stats = results[key]
            print(f"  {k_label}: 有效={stats['n_valid']}, "
                  f"正例={stats['n_positive']}, "
                  f"负例={stats['n_negative']}, "
                  f"正例率={stats['positive_rate']:.4f}")

    print()
    print(f"  类别权重 (用于 loss): {results['class_weights_for_loss']}")
    print("  " + "-" * 60)
