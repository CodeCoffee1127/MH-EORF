"""
monotonicity.py

计算单调性违反率 (MVR)。

MVR 测量校准后累积风险是否满足:
Q_tilde_{i,t,1} <= Q_tilde_{i,t,2} <= Q_tilde_{i,t,3}
"""

import numpy as np
from typing import Tuple


def compute_mvr(
    Q_tilde: np.ndarray,
    epsilon_num: float = 1e-8,
) -> Tuple[float, int, int]:
    """
    计算单调性违反率。

    Args:
        Q_tilde: [N, 3]，校准后累积风险
        epsilon_num: 数值容差

    Returns:
        (mvr, n_violations, n_total)
    """
    # 检查 Q_tilde[:, 0] <= Q_tilde[:, 1] <= Q_tilde[:, 2]
    # 允许 epsilon_num 的数值误差
    violation_1_2 = Q_tilde[:, 0] > Q_tilde[:, 1] + epsilon_num
    violation_2_3 = Q_tilde[:, 1] > Q_tilde[:, 2] + epsilon_num

    # 任一反违反都算违反
    violations = violation_1_2 | violation_2_3

    n_violations = int(violations.sum())
    n_total = len(Q_tilde)
    mvr = n_violations / n_total if n_total > 0 else 0.0

    return mvr, n_violations, n_total


def print_mvr_summary(mvr: float, n_violations: int, n_total: int):
    """
    打印 MVR 摘要。

    Args:
        mvr: 单调性违反率
        n_violations: 违反样本数
        n_total: 总样本数
    """
    print(f"\n  单调性违反率 (MVR):")
    print(f"    MVR: {mvr:.6f}")
    print(f"    Violations: {n_violations} / {n_total}")
    print(f"    Status: {'PASS' if mvr == 0 else 'FAIL'}")
