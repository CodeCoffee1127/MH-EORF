"""
correctness.py

计算 Expected Calibration Error (ECE)。

ECE 测量预测概率与实际频率之间的差距。
"""

import numpy as np
from typing import Dict


def compute_ece(
    Q_tilde: np.ndarray,
    y_cum: np.ndarray,
    valid_mask_cum: np.ndarray,
    n_bins: int = 10,
) -> Dict:
    """
    计算 ECE。

    ECE = sum_{b=1}^{B} (n_b / N) * |mean(Q_tilde_b) - mean(y_b)|

    Args:
        Q_tilde: [N]，校准后累积风险
        y_cum: [N]，标签
        valid_mask_cum: [N]，有效掩码
        n_bins: bin 数量

    Returns:
        ECE 字典
    """
    mask = valid_mask_cum == 1
    Q_valid = Q_tilde[mask]
    y_valid = y_cum[mask]

    n_valid = int(mask.sum())

    if n_valid == 0:
        return {"ece": 0.0, "n_bins": n_bins, "n_valid": 0}

    # 定义 bin 边界
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)

    ece = 0.0

    for b in range(n_bins):
        # bin 边界
        low = bin_edges[b]
        high = bin_edges[b + 1]

        # 落入 bin 的样本
        if b == n_bins - 1:
            # 最后一个 bin 包含右边界
            in_bin = (Q_valid >= low) & (Q_valid <= high)
        else:
            in_bin = (Q_valid >= low) & (Q_valid < high)

        n_b = int(in_bin.sum())

        if n_b > 0:
            # bin 内的平均预测和实际频率
            mean_pred = Q_valid[in_bin].mean()
            mean_actual = y_valid[in_bin].mean()

            # 加权绝对误差
            ece += (n_b / n_valid) * abs(mean_pred - mean_actual)

    return {
        "ece": float(ece),
        "n_bins": n_bins,
        "n_valid": n_valid,
    }


def compute_ece_by_horizon(
    Q_tilde: np.ndarray,
    y_cum: np.ndarray,
    valid_mask_cum: np.ndarray,
) -> Dict:
    """
    按 horizon 计算 ECE。

    h=1 使用 8 bins，h=2/h=3 使用 10 bins。

    Args:
        Q_tilde: [N, 3]
        y_cum: [N, 3]
        valid_mask_cum: [N, 3]

    Returns:
        按 horizon 的 ECE 字典
    """
    ece_results = {}

    for h_idx, h in enumerate([1, 2, 3]):
        # h=1 使用 8 bins，h=2/h=3 使用 10 bins
        n_bins = 8 if h == 1 else 10

        ece_results[f"h{h}"] = compute_ece(
            Q_tilde=Q_tilde[:, h_idx],
            y_cum=y_cum[:, h_idx],
            valid_mask_cum=valid_mask_cum[:, h_idx],
            n_bins=n_bins,
        )

    return ece_results


def print_ece_summary(ece_results: Dict):
    """
    打印 ECE 摘要。

    Args:
        ece_results: compute_ece_by_horizon 的返回结果
    """
    print("\n  Expected Calibration Error (ECE):")
    print("  " + "-" * 50)
    print(f"  {'Horizon':<10} {'ECE':<10} {'N Bins':<10} {'N Valid':<10}")
    print("  " + "-" * 50)

    for h in [1, 2, 3]:
        key = f"h{h}"
        ece = ece_results[key]
        print(f"  h={h:<8} {ece['ece']:<10.6f} {ece['n_bins']:<10} {ece['n_valid']:<10}")

    print("  " + "-" * 50)
