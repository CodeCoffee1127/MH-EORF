"""
threshold.py

多视野预警阈值搜索。

对每个 horizon h，在 cal-dev 上搜索阈值 θ_h：
θ_h = argmax_{θ in [0,1]} F1(I(Q_tilde >= θ), y)

若多个阈值获得相同 F1，选择更大的阈值。
"""

import numpy as np
import json
from pathlib import Path
from typing import Dict, Tuple
from sklearn.metrics import f1_score

OUTPUT_DIR = Path("D:/SL-RDAF/outputs/calibration")


def search_threshold(
    Q_tilde: np.ndarray,
    y: np.ndarray,
    valid_mask: np.ndarray,
    n_points: int = 1001,
) -> Tuple[float, Dict]:
    """
    搜索最优阈值。

    Args:
        Q_tilde: [N]，校准后的累积风险
        y: [N]，标签
        valid_mask: [N]，有效掩码
        n_points: 阈值搜索点数

    Returns:
        (theta_best, stats)
    """
    # 只使用有效行
    mask = valid_mask == 1
    Q_valid = Q_tilde[mask]
    y_valid = y[mask]

    # 移除 NaN
    valid_idx = ~np.isnan(y_valid)
    Q_valid = Q_valid[valid_idx]
    y_valid = y_valid[valid_idx]

    if len(Q_valid) == 0:
        print(f"  警告: 没有有效样本，使用 θ=0.0")
        return 0.0, {"n_valid": 0, "best_f1": 0.0}

    # 阈值搜索空间
    thresholds = np.linspace(0.0, 1.0, n_points)

    best_f1 = -1.0
    best_theta = 0.0

    for theta in thresholds:
        y_pred = (Q_valid >= theta).astype(int)

        # 检查是否有正例预测
        if y_pred.sum() == 0:
            continue

        f1 = f1_score(y_valid, y_pred, zero_division=0)

        # 若 F1 相同或更好，选择更大的阈值（降低过度预警）
        if f1 >= best_f1:
            best_f1 = f1
            best_theta = theta

    stats = {
        "n_valid": int(mask.sum()),
        "best_f1": float(best_f1),
        "best_theta": float(best_theta),
        "thresholds_searched": int(n_points),
    }

    return best_theta, stats


def search_all_thresholds(
    Q_tilde: np.ndarray,
    y_cum: np.ndarray,
    valid_mask_cum: np.ndarray,
    output_dir: Path = OUTPUT_DIR,
) -> Tuple[Dict, Dict]:
    """
    搜索三个 horizons 的阈值。

    Args:
        Q_tilde: [N, 3]，校准后的累积风险
        y_cum: [N, 3]，累积风险标签
        valid_mask_cum: [N, 3]，有效掩码
        output_dir: 输出目录

    Returns:
        (thresholds_dict, stats_dict)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    thresholds = {}
    stats = {}

    for h_idx, h in enumerate([1, 2, 3]):
        print(f"\n  搜索 horizon h={h} 的阈值 θ_{h}...")

        theta_h, stats_h = search_threshold(
            Q_tilde=Q_tilde[:, h_idx],
            y=y_cum[:, h_idx],
            valid_mask=valid_mask_cum[:, h_idx],
            n_points=1001,
        )

        thresholds[f"theta_{h}"] = float(theta_h)
        stats[f"theta_{h}"] = stats_h

        print(f"    θ_{h} = {theta_h:.4f}, F1 = {stats_h['best_f1']:.4f}")

    # 保存阈值
    thresholds_output = {
        "theta_1": thresholds["theta_1"],
        "theta_2": thresholds["theta_2"],
        "theta_3": thresholds["theta_3"],
        "tie_break": "choose_larger_threshold",
        "source": "cal-dev only",
    }

    output_path = output_dir / "theta_h.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(thresholds_output, f, indent=2, ensure_ascii=False)

    print(f"\n  阈值已保存: {output_path}")

    return thresholds, stats


def apply_thresholds(
    Q_tilde: np.ndarray,
    thresholds: Dict,
) -> np.ndarray:
    """
    应用阈值生成预警预测。

    Args:
        Q_tilde: [N, 3] 或 [B, T, 3]，校准后的累积风险
        thresholds: {theta_1, theta_2, theta_3}

    Returns:
        y_hat: 与 Q_tilde 相同 shape，预警预测
    """
    y_hat = np.zeros_like(Q_tilde, dtype=int)

    for h_idx, h in enumerate([1, 2, 3]):
        theta = thresholds[f"theta_{h}"]
        y_hat[..., h_idx] = (Q_tilde[..., h_idx] >= theta).astype(int)

    return y_hat
