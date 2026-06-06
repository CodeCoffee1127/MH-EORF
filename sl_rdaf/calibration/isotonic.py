"""
isotonic.py

Isotonic 校准器。

对每个 lead step k，使用 cal-dev 拟合 isotonic 映射 f_k:
f_k = argmin_{f in F_mono} sum (y_haz - f(q))^2
"""

import numpy as np
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from sklearn.isotonic import IsotonicRegression

OUTPUT_DIR = Path("D:/SL-RDAF/outputs/calibration")


class IsotonicCalibrator:
    """
    Isotonic 校准器。

    使用 sklearn.isotonic.IsotonicRegression 拟合单调递增映射。
    """

    def __init__(self, lead_step: int):
        """
        Args:
            lead_step: lead step k (1, 2, 或 3)
        """
        self.lead_step = lead_step
        self.ir = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True)
        self.fitted = False

    def fit(
        self,
        q: np.ndarray,
        y_haz: np.ndarray,
        valid_mask: np.ndarray,
    ):
        """
        拟合 isotonic 校准器。

        Args:
            q: 预测的单步风险 [N]
            y_haz: hazard 标签 [N]
            valid_mask: 有效掩码 [N]
        """
        # 只使用有效行
        mask = valid_mask == 1
        q_valid = q[mask]
        y_valid = y_haz[mask]

        if len(q_valid) == 0:
            print(f"  警告: lead step {self.lead_step} 没有有效样本，跳过拟合")
            self.fitted = False
            return

        # 拟合
        self.ir.fit(q_valid, y_valid)
        self.fitted = True

        print(f"  Isotonic 校准器 f_{self.lead_step} 拟合完成: {len(q_valid)} 有效样本")

    def transform(self, q: np.ndarray) -> np.ndarray:
        """
        应用校准映射。

        Args:
            q: 预测的单步风险 [N]

        Returns:
            校准后的风险 q_tilde [N]
        """
        if not self.fitted:
            # 未拟合，返回原始值
            return q

        q_tilde = self.ir.transform(q)

        # 确保值域在 [0, 1]
        q_tilde = np.clip(q_tilde, 0.0, 1.0)

        return q_tilde

    def save(self, output_path: Path):
        """
        保存校准器。

        Args:
            output_path: 保存路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            pickle.dump({
                "lead_step": self.lead_step,
                "isotonic_regression": self.ir,
                "fitted": self.fitted,
            }, f)

        print(f"  校准器已保存: {output_path}")

    @staticmethod
    def load(load_path: Path) -> "IsotonicCalibrator":
        """
        加载校准器。

        Args:
            load_path: 加载路径

        Returns:
            IsotonicCalibrator 实例
        """
        with open(load_path, "rb") as f:
            data = pickle.load(f)

        calibrator = IsotonicCalibrator(lead_step=data["lead_step"])
        calibrator.ir = data["isotonic_regression"]
        calibrator.fitted = data["fitted"]

        return calibrator


def fit_isotonic_calibrators(
    q: np.ndarray,
    y_haz: np.ndarray,
    valid_mask_haz: np.ndarray,
    output_dir: Path = OUTPUT_DIR,
) -> Tuple[List[IsotonicCalibrator], Dict]:
    """
    拟合三个 lead step 的 isotonic 校准器。

    Args:
        q: [N, 3]，预测的单步风险 q_{i,t,k}
        y_haz: [N, 3]，hazard 标签
        valid_mask_haz: [N, 3]，有效掩码
        output_dir: 输出目录

    Returns:
        (calibrators, stats)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    calibrators = []
    stats = {}

    for k_idx, k in enumerate([1, 2, 3]):
        print(f"\n  拟合 isotonic 校准器 f_{k}...")

        calibrator = IsotonicCalibrator(lead_step=k)
        calibrator.fit(
            q=q[:, k_idx],
            y_haz=y_haz[:, k_idx],
            valid_mask=valid_mask_haz[:, k_idx],
        )

        if calibrator.fitted:
            # 保存
            save_path = output_dir / f"f_{k}.pkl"
            calibrator.save(save_path)

            # 统计
            stats[f"f_{k}"] = {
                "fitted": True,
                "n_samples": int((valid_mask_haz[:, k_idx] == 1).sum()),
                "save_path": str(save_path),
            }
        else:
            stats[f"f_{k}"] = {
                "fitted": False,
                "n_samples": 0,
                "save_path": None,
            }

        calibrators.append(calibrator)

    return calibrators, stats


def apply_isotonic_calibrators(
    calibrators: List[IsotonicCalibrator],
    q: np.ndarray,
) -> np.ndarray:
    """
    应用 isotonic 校准器。

    Args:
        calibrators: [f_1, f_2, f_3]
        q: [N, 3]，预测的单步风险

    Returns:
        q_tilde: [N, 3]，校准后的风险
    """
    q_tilde = np.zeros_like(q)

    for k_idx, calibrator in enumerate(calibrators):
        q_tilde[:, k_idx] = calibrator.transform(q[:, k_idx])

    return q_tilde


def compute_calibrated_cumulative_risk(q_tilde: np.ndarray) -> np.ndarray:
    """
    计算校准后的累积风险。

    Q_tilde_{i,t,h} = 1 - prod_{k=1}^{h} (1 - q_tilde_{i,t,k})

    Args:
        q_tilde: [N, 3]，校准后的单步风险

    Returns:
        Q_tilde: [N, 3]，校准后的累积风险
    """
    # 生存概率
    survival = 1.0 - q_tilde  # [N, 3]

    # 累积生存概率
    cum_survival = np.cumprod(survival, axis=1)  # [N, 3]

    # 累积风险
    Q_tilde = 1.0 - cum_survival  # [N, 3]

    return Q_tilde
