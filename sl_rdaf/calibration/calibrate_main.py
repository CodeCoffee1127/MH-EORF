"""
calibrate_main.py

校准主流程。

在 cal-dev 上：
1. 用冻结模型预测 q_{i,t,k}, Q_{i,t,h}
2. 拟合 isotonic 校准器 f_k
3. 计算校准后的 Q_tilde
4. 搜索预警阈值 θ_h
"""

import pandas as pd
import numpy as np
import torch
from pathlib import Path
from typing import Dict, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sl_rdaf.model.sl_rdaf import MHEORF
from sl_rdaf.calibration.isotonic import (
    fit_isotonic_calibrators,
    apply_isotonic_calibrators,
    compute_calibrated_cumulative_risk,
)
from sl_rdaf.calibration.threshold import search_all_thresholds
from sl_rdaf.data.schema import (
    SAMPLE_ID_COL, STEP_T_COL,
    Y_I_T_H1, Y_I_T_H2, Y_I_T_H3,
    Y_HAZ_I_T_K1, Y_HAZ_I_T_K2, Y_HAZ_I_T_K3,
    VALID_H1, VALID_H2, VALID_H3,
    VALID_HAZ_K1, VALID_HAZ_K2, VALID_HAZ_K3,
)

OUTPUT_DIR = Path("D:/SL-RDAF/outputs/calibration")


def predict_on_cal_dev(
    model: MHEORF,
    cal_df: pd.DataFrame,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    """
    在 cal-dev 上预测。

    Args:
        model: 冻结的模型
        cal_df: cal-dev DataFrame
        device: 计算设备

    Returns:
        (q_all, Q_all, y_haz_all, y_cum_all, sample_info)
    """
    print("\n[Step 1] 在 cal-dev 上预测...")

    model.eval()

    # 按 sample_id 构建序列
    samples = []
    sample_ids = []
    time_steps = []

    for sample_id, group in cal_df.groupby(SAMPLE_ID_COL):
        group = group.sort_values(STEP_T_COL)

        from sl_rdaf.data.schema import X_DIR_COLS, X_RES_COLS

        x_dir = torch.from_numpy(group[X_DIR_COLS].values.astype(np.float32)).unsqueeze(0).to(device)
        x_res = torch.from_numpy(group[X_RES_COLS].values.astype(np.float32)).unsqueeze(0).to(device)

        with torch.no_grad():
            q, Q = model(x_dir, x_res, mask_time=None)

        # 移到 CPU
        q_np = q.squeeze(0).cpu().numpy()  # [T, 3]
        Q_np = Q.squeeze(0).cpu().numpy()  # [T, 3]

        y_haz = group[[Y_HAZ_I_T_K1, Y_HAZ_I_T_K2, Y_HAZ_I_T_K3]].values.astype(np.float32)
        y_cum = group[[Y_I_T_H1, Y_I_T_H2, Y_I_T_H3]].values.astype(np.float32)

        samples.append((q_np, Q_np, y_haz, y_cum))
        sample_ids.extend([sample_id] * len(group))
        time_steps.extend(group[STEP_T_COL].values)

    # 拼接所有样本
    q_all = np.concatenate([s[0] for s in samples], axis=0)
    Q_all = np.concatenate([s[1] for s in samples], axis=0)
    y_haz_all = np.concatenate([s[2] for s in samples], axis=0)
    y_cum_all = np.concatenate([s[3] for s in samples], axis=0)

    # 构建 sample_info DataFrame
    sample_info = pd.DataFrame({
        SAMPLE_ID_COL: sample_ids,
        STEP_T_COL: time_steps,
    })

    print(f"  cal-dev 预测完成: {q_all.shape[0]} 行")

    return q_all, Q_all, y_haz_all, y_cum_all, sample_info


def save_uncalibrated_predictions(
    sample_info: pd.DataFrame,
    q_all: np.ndarray,
    Q_all: np.ndarray,
    y_haz_all: np.ndarray,
    y_cum_all: np.ndarray,
    valid_mask_haz: np.ndarray,
    valid_mask_cum: np.ndarray,
    output_dir: Path = OUTPUT_DIR,
):
    """
    保存未校准预测。

    Args:
        sample_info: sample_id 和 t
        q_all: [N, 3]，单步风险
        Q_all: [N, 3]，累积风险
        y_haz_all: [N, 3]，hazard 标签
        y_cum_all: [N, 3]，累积风险标签
        valid_mask_haz: [N, 3]
        valid_mask_cum: [N, 3]
        output_dir: 输出目录
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    df = sample_info.copy()

    # 添加预测
    df["q_i_t_k1"] = q_all[:, 0]
    df["q_i_t_k2"] = q_all[:, 1]
    df["q_i_t_k3"] = q_all[:, 2]

    df["Q_i_t_h1"] = Q_all[:, 0]
    df["Q_i_t_h2"] = Q_all[:, 1]
    df["Q_i_t_h3"] = Q_all[:, 2]

    # 添加标签
    df["y_haz_i_t_k1"] = y_haz_all[:, 0]
    df["y_haz_i_t_k2"] = y_haz_all[:, 1]
    df["y_haz_i_t_k3"] = y_haz_all[:, 2]

    df["y_i_t_h1"] = y_cum_all[:, 0]
    df["y_i_t_h2"] = y_cum_all[:, 1]
    df["y_i_t_h3"] = y_cum_all[:, 2]

    # 添加 valid mask
    df["valid_haz_k1"] = valid_mask_haz[:, 0]
    df["valid_haz_k2"] = valid_mask_haz[:, 1]
    df["valid_haz_k3"] = valid_mask_haz[:, 2]

    df["valid_h1"] = valid_mask_cum[:, 0]
    df["valid_h2"] = valid_mask_cum[:, 1]
    df["valid_h3"] = valid_mask_cum[:, 2]

    output_path = output_dir / "cal_dev_uncalibrated_predictions.csv"
    df.to_csv(output_path, index=False)

    print(f"  未校准预测已保存: {output_path}")


def save_calibrated_predictions(
    sample_info: pd.DataFrame,
    q_tilde_all: np.ndarray,
    Q_tilde_all: np.ndarray,
    output_dir: Path = OUTPUT_DIR,
):
    """
    保存校准后预测。

    Args:
        sample_info: sample_id 和 t
        q_tilde_all: [N, 3]，校准后单步风险
        Q_tilde_all: [N, 3]，校准后累积风险
        output_dir: 输出目录
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    df = sample_info.copy()

    # 添加校准后预测
    df["q_tilde_i_t_k1"] = q_tilde_all[:, 0]
    df["q_tilde_i_t_k2"] = q_tilde_all[:, 1]
    df["q_tilde_i_t_k3"] = q_tilde_all[:, 2]

    df["Q_tilde_i_t_h1"] = Q_tilde_all[:, 0]
    df["Q_tilde_i_t_h2"] = Q_tilde_all[:, 1]
    df["Q_tilde_i_t_h3"] = Q_tilde_all[:, 2]

    output_path = output_dir / "cal_dev_calibrated_predictions.csv"
    df.to_csv(output_path, index=False)

    print(f"  校准后预测已保存: {output_path}")


def verify_monotonicity(Q_tilde: np.ndarray) -> bool:
    """
    验证校准后累积风险单调性。

    Q_tilde_{i,t,1} <= Q_tilde_{i,t,2} <= Q_tilde_{i,t,3}

    Args:
        Q_tilde: [N, 3]

    Returns:
        是否全部满足
    """
    mono_1_2 = (Q_tilde[:, 0] <= Q_tilde[:, 1] + 1e-8).all()
    mono_2_3 = (Q_tilde[:, 1] <= Q_tilde[:, 2] + 1e-8).all()

    return mono_1_2 and mono_2_3


def generate_calibration_report(
    cal_df: pd.DataFrame,
    calibrator_stats: Dict,
    threshold_stats: Dict,
    thresholds: Dict,
    monotonicity_pass: bool,
) -> str:
    """
    生成校准报告。

    Returns:
        Markdown 报告文本
    """
    lines = []

    lines.append("# Phase 3 校准报告")
    lines.append("")
    lines.append("## 1. 校准数据")
    lines.append("")
    lines.append(f"- Cal-dev 样本数: {cal_df[SAMPLE_ID_COL].nunique()}")
    lines.append(f"- Cal-dev 行数: {len(cal_df)}")
    lines.append("")

    lines.append("## 2. Isotonic 校准器 f_k")
    lines.append("")
    lines.append("| Lead Step | Fitted | N Samples |")
    lines.append("|-----------|--------|-----------|")
    for k in [1, 2, 3]:
        key = f"f_{k}"
        stats = calibrator_stats[key]
        lines.append(f"| k={k} | {'✓' if stats['fitted'] else '✗'} | {stats['n_samples']} |")
    lines.append("")

    lines.append("## 3. 预警阈值 θ_h")
    lines.append("")
    lines.append("| Horizon | θ_h | Best F1 | N Valid |")
    lines.append("|---------|-----|---------|---------|")
    for h in [1, 2, 3]:
        key = f"theta_{h}"
        theta = thresholds[key]
        stats = threshold_stats[key]
        lines.append(f"| h={h} | {theta:.4f} | {stats['best_f1']:.4f} | {stats['n_valid']} |")
    lines.append("")

    lines.append("## 4. 单调性验证")
    lines.append("")
    lines.append(f"- Q_tilde 单调性 (h1 <= h2 <= h3): {'✓ PASS' if monotonicity_pass else '✗ FAIL'}")
    lines.append("")

    lines.append("## 5. 校准产物")
    lines.append("")
    lines.append("- f_1.pkl, f_2.pkl, f_3.pkl: isotonic 校准器")
    lines.append("- theta_h.json: 预警阈值")
    lines.append("- cal_dev_uncalibrated_predictions.csv: 未校准预测")
    lines.append("- cal_dev_calibrated_predictions.csv: 校准后预测")
    lines.append("")

    lines.append("## 6. 重要说明")
    lines.append("")
    lines.append("- cal-dev 仅用于拟合 f_k 和冻结 θ_h")
    lines.append("- 未使用 cal-dev 进行模型参数更新")
    lines.append("- 未使用 cal-dev 进行 early stopping、学习率选择或模型选择")
    lines.append("- heldout 完全隔离，未访问")
    lines.append("")

    return "\n".join(lines)


def main(
    model: MHEORF,
    cal_df: pd.DataFrame,
    device: torch.device,
) -> Tuple[Dict, Dict]:
    """
    主执行流程。

    Args:
        model: 冻结的模型
        cal_df: cal-dev DataFrame
        device: 计算设备

    Returns:
        (calibrator_stats, threshold_stats)
    """
    print("=" * 70)
    print("SL-RDAF Phase 3: cal-dev 校准")
    print("=" * 70)

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 在 cal-dev 上预测
    q_all, Q_all, y_haz_all, y_cum_all, sample_info = predict_on_cal_dev(model, cal_df, device)

    # 提取 valid masks
    valid_mask_haz = cal_df[[VALID_HAZ_K1, VALID_HAZ_K2, VALID_HAZ_K3]].values.astype(np.float32)
    valid_mask_cum = cal_df[[VALID_H1, VALID_H2, VALID_H3]].values.astype(np.float32)

    # 2. 保存未校准预测
    save_uncalibrated_predictions(
        sample_info, q_all, Q_all, y_haz_all, y_cum_all,
        valid_mask_haz, valid_mask_cum,
    )

    # 3. 拟合 isotonic 校准器
    print("\n[Step 2] 拟合 isotonic 校准器...")
    calibrators, calibrator_stats = fit_isotonic_calibrators(
        q_all, y_haz_all, valid_mask_haz, OUTPUT_DIR
    )

    # 4. 应用校准器
    print("\n[Step 3] 应用校准器...")
    q_tilde_all = apply_isotonic_calibrators(calibrators, q_all)
    Q_tilde_all = compute_calibrated_cumulative_risk(q_tilde_all)

    # 验证单调性
    monotonicity_pass = verify_monotonicity(Q_tilde_all)
    print(f"  单调性验证: {'PASS' if monotonicity_pass else 'FAIL'}")

    # 5. 保存校准后预测
    save_calibrated_predictions(sample_info, q_tilde_all, Q_tilde_all)

    # 6. 搜索阈值
    print("\n[Step 4] 搜索预警阈值...")
    thresholds, threshold_stats = search_all_thresholds(
        Q_tilde_all, y_cum_all, valid_mask_cum, OUTPUT_DIR
    )

    # 7. 生成报告
    print("\n[Step 5] 生成校准报告...")
    report_md = generate_calibration_report(
        cal_df, calibrator_stats, threshold_stats, thresholds, monotonicity_pass
    )

    report_path = OUTPUT_DIR / "calibration_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"  校准报告已保存: {report_path}")

    # 8. 保存摘要
    summary = {
        "cal_dev_samples": int(cal_df[SAMPLE_ID_COL].nunique()),
        "cal_dev_rows": int(len(cal_df)),
        "calibrator_stats": calibrator_stats,
        "thresholds": thresholds,
        "threshold_stats": threshold_stats,
        "monotonicity_pass": monotonicity_pass,
    }

    summary_path = OUTPUT_DIR / "calibration_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"  校准摘要已保存: {summary_path}")

    # 9. 控制台输出
    print("\n" + "=" * 70)
    print("[SL-RDAF Phase 3 Calibration Completed]")
    print("=" * 70)
    print(f"\nCal-dev:")
    print(f"  samples: {cal_df[SAMPLE_ID_COL].nunique()}")
    print(f"  rows: {len(cal_df)}")
    print(f"  f_1 fitted: {'PASS' if calibrator_stats['f_1']['fitted'] else 'FAIL'}")
    print(f"  f_2 fitted: {'PASS' if calibrator_stats['f_2']['fitted'] else 'FAIL'}")
    print(f"  f_3 fitted: {'PASS' if calibrator_stats['f_3']['fitted'] else 'FAIL'}")
    print(f"  θ_1: {thresholds['theta_1']:.4f}")
    print(f"  θ_2: {thresholds['theta_2']:.4f}")
    print(f"  θ_3: {thresholds['theta_3']:.4f}")
    print(f"  monotonicity: {'PASS' if monotonicity_pass else 'FAIL'}")
    print(f"\nOutput files:")
    print(f"  {OUTPUT_DIR / 'f_1.pkl'}")
    print(f"  {OUTPUT_DIR / 'f_2.pkl'}")
    print(f"  {OUTPUT_DIR / 'f_3.pkl'}")
    print(f"  {OUTPUT_DIR / 'theta_h.json'}")
    print(f"  {OUTPUT_DIR / 'cal_dev_uncalibrated_predictions.csv'}")
    print(f"  {OUTPUT_DIR / 'cal_dev_calibrated_predictions.csv'}")
    print(f"  {OUTPUT_DIR / 'calibration_report.md'}")
    print(f"  {OUTPUT_DIR / 'calibration_summary.json'}")
    print("=" * 70)

    return calibrator_stats, threshold_stats


if __name__ == "__main__":
    # 独立运行时，加载模型和数据
    import json

    # 加载模型
    step = torch.load(
        Path("D:/SL-RDAF/outputs/training/model_final.pt"),
        map_location="cpu",
    )

    model = MHEORF(
        x_dir_dim=5,
        x_res_dim=11,
        state_dim=8,
        n_horizons=3,
        activation="tanh",
    )
    model.load_state_dict(step["model_state_dict"])

    # 加载 cal-dev 数据（需要重新处理）
    from sl_rdaf.training.train_main import load_and_process_data
    _, cal_df, _ = load_and_process_data()

    device = torch.device("cpu")

    main(model, cal_df, device)
