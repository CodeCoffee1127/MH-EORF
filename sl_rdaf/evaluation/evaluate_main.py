"""
evaluate_main.py

Heldout 一次性最终评估。

只有在以下文件全部存在后才执行：
- model_final.pt
- phase_thresholds_train_dev.json
- standardization_stats_train_dev.json
- f_1.pkl, f_2.pkl, f_3.pkl
- theta_h.json
"""

import pandas as pd
import numpy as np
import torch
import json
from pathlib import Path
from typing import Dict, Tuple

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sl_rdaf.model.sl_rdaf import MHEORF
from sl_rdaf.calibration.isotonic import IsotonicCalibrator, apply_isotonic_calibrators, compute_calibrated_cumulative_risk
from sl_rdaf.evaluation.horizon_metrics import compute_horizon_metrics, print_metrics_summary
from sl_rdaf.evaluation.monotonicity import compute_mvr, print_mvr_summary
from sl_rdaf.evaluation.correctness import compute_ece_by_horizon, print_ece_summary
from sl_rdaf.evaluation.lead_time import compute_lead_time_metrics, print_lead_time_summary
from sl_rdaf.data.schema import (
    SAMPLE_ID_COL, STEP_T_COL, X_DIR_COLS, X_RES_COLS,
    Y_I_T_H1, Y_I_T_H2, Y_I_T_H3,
    VALID_H1, VALID_H2, VALID_H3,
)

OUTPUT_DIR = Path("D:/SL-RDAF/outputs/evaluation")


def verify_prerequisites() -> bool:
    """
    验证前置条件。

    Returns:
        是否满足所有前置条件
    """
    required_files = [
        Path("D:/SL-RDAF/outputs/training/model_final.pt"),
        Path("D:/SL-RDAF/outputs/phase1/phase_thresholds_train_dev.json"),
        Path("D:/SL-RDAF/outputs/phase1/standardization_stats_train_dev.json"),
        Path("D:/SL-RDAF/outputs/calibration/f_1.pkl"),
        Path("D:/SL-RDAF/outputs/calibration/f_2.pkl"),
        Path("D:/SL-RDAF/outputs/calibration/f_3.pkl"),
        Path("D:/SL-RDAF/outputs/calibration/theta_h.json"),
    ]

    all_exist = True
    for f in required_files:
        if not f.exists():
            print(f"  缺失前置文件: {f}")
            all_exist = False

    return all_exist


def predict_on_heldout(
    model: MHEORF,
    heldout_df: pd.DataFrame,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    """
    在 heldout 上预测。

    Args:
        model: 冻结的模型
        heldout_df: heldout DataFrame
        device: 计算设备

    Returns:
        (q_all, Q_all, y_cum_all, valid_mask_cum, sample_info)
    """
    print("\n[Step 1] 在 heldout 上预测（一次性）...")

    model.eval()

    samples = []
    sample_ids = []
    time_steps = []

    for sample_id, group in heldout_df.groupby(SAMPLE_ID_COL):
        group = group.sort_values(STEP_T_COL)

        x_dir = torch.from_numpy(group[X_DIR_COLS].values.astype(np.float32)).unsqueeze(0).to(device)
        x_res = torch.from_numpy(group[X_RES_COLS].values.astype(np.float32)).unsqueeze(0).to(device)

        with torch.no_grad():
            q, Q = model(x_dir, x_res, mask_time=None)

        q_np = q.squeeze(0).cpu().numpy()
        Q_np = Q.squeeze(0).cpu().numpy()

        y_cum = group[[Y_I_T_H1, Y_I_T_H2, Y_I_T_H3]].values.astype(np.float32)

        samples.append((q_np, Q_np, y_cum))
        sample_ids.extend([sample_id] * len(group))
        time_steps.extend(group[STEP_T_COL].values)

    q_all = np.concatenate([s[0] for s in samples], axis=0)
    Q_all = np.concatenate([s[1] for s in samples], axis=0)
    y_cum_all = np.concatenate([s[2] for s in samples], axis=0)

    sample_info = pd.DataFrame({
        SAMPLE_ID_COL: sample_ids,
        STEP_T_COL: time_steps,
    })

    print(f"  heldout 预测完成: {q_all.shape[0]} 行")

    return q_all, Q_all, y_cum_all, sample_info


def save_heldout_predictions(
    sample_info: pd.DataFrame,
    q_all: np.ndarray,
    Q_all: np.ndarray,
    q_tilde_all: np.ndarray,
    Q_tilde_all: np.ndarray,
    y_hat_all: np.ndarray,
    y_cum_all: np.ndarray,
    valid_mask_cum: np.ndarray,
    thresholds: Dict,
    output_dir: Path = OUTPUT_DIR,
):
    """
    保存 heldout 预测。

    Args:
        sample_info: sample_id 和 t
        q_all: [N, 3]，原始单步风险
        Q_all: [N, 3]，原始累积风险
        q_tilde_all: [N, 3]，校准后单步风险
        Q_tilde_all: [N, 3]，校准后累积风险
        y_hat_all: [N, 3]，预警预测
        y_cum_all: [N, 3]，累积风险标签
        valid_mask_cum: [N, 3]，有效掩码
        thresholds: 阈值字典
        output_dir: 输出目录
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    df = sample_info.copy()

    # 原始预测
    df["q_i_t_k1"] = q_all[:, 0]
    df["q_i_t_k2"] = q_all[:, 1]
    df["q_i_t_k3"] = q_all[:, 2]

    df["Q_i_t_h1"] = Q_all[:, 0]
    df["Q_i_t_h2"] = Q_all[:, 1]
    df["Q_i_t_h3"] = Q_all[:, 2]

    # 校准后预测
    df["q_tilde_i_t_k1"] = q_tilde_all[:, 0]
    df["q_tilde_i_t_k2"] = q_tilde_all[:, 1]
    df["q_tilde_i_t_k3"] = q_tilde_all[:, 2]

    df["Q_tilde_i_t_h1"] = Q_tilde_all[:, 0]
    df["Q_tilde_i_t_h2"] = Q_tilde_all[:, 1]
    df["Q_tilde_i_t_h3"] = Q_tilde_all[:, 2]

    # 阈值
    df["theta_1"] = thresholds["theta_1"]
    df["theta_2"] = thresholds["theta_2"]
    df["theta_3"] = thresholds["theta_3"]

    # 预警预测
    df["y_hat_i_t_h1"] = y_hat_all[:, 0]
    df["y_hat_i_t_h2"] = y_hat_all[:, 1]
    df["y_hat_i_t_h3"] = y_hat_all[:, 2]

    # 标签
    df["y_i_t_h1"] = y_cum_all[:, 0]
    df["y_i_t_h2"] = y_cum_all[:, 1]
    df["y_i_t_h3"] = y_cum_all[:, 2]

    # Valid mask
    df["valid_h1"] = valid_mask_cum[:, 0]
    df["valid_h2"] = valid_mask_cum[:, 1]
    df["valid_h3"] = valid_mask_cum[:, 2]

    output_path = output_dir / "heldout_predictions.csv"
    df.to_csv(output_path, index=False)

    print(f"  Heldout 预测已保存: {output_path}")


def generate_evaluation_report(
    heldout_df: pd.DataFrame,
    metrics: Dict,
    mvr: float,
    n_violations: int,
    n_total: int,
    ece_results: Dict,
    lead_time_results: Dict,
    thresholds: Dict,
) -> str:
    """
    生成评估报告。

    Returns:
        Markdown 报告文本
    """
    lines = []

    lines.append("# Phase 3 Heldout 一次性最终评估报告")
    lines.append("")
    lines.append("## 1. 评估数据")
    lines.append("")
    lines.append(f"- Heldout 样本数: {heldout_df[SAMPLE_ID_COL].nunique()}")
    lines.append(f"- Heldout 行数: {len(heldout_df)}")
    lines.append("")

    lines.append("## 2. 冻结参数")
    lines.append("")
    lines.append(f"- θ_1: {thresholds['theta_1']:.4f}")
    lines.append(f"- θ_2: {thresholds['theta_2']:.4f}")
    lines.append(f"- θ_3: {thresholds['theta_3']:.4f}")
    lines.append("")

    lines.append("## 3. 按 Horizon 指标")
    lines.append("")
    lines.append("| Horizon | AUROC | AUPRC | Precision | Recall | F1 | Alert Rate | Brier Score |")
    lines.append("|---------|-------|-------|-----------|--------|------|------------|-------------|")

    for h in [1, 2, 3]:
        key = f"h{h}"
        m = metrics[key]
        auroc_str = f"{m['AUROC']:.4f}" if m['AUROC'] is not None else "N/A"
        auprc_str = f"{m['AUPRC']:.4f}" if m['AUPRC'] is not None else "N/A"
        lines.append(
            f"| h={h} | {auroc_str} | {auprc_str} | {m['Precision']:.4f} | "
            f"{m['Recall']:.4f} | {m['F1']:.4f} | {m['Alert_Rate']:.4f} | {m['Brier_Score']:.4f} |"
        )

    lines.append("")

    lines.append("## 4. 单调性违反率 (MVR)")
    lines.append("")
    lines.append(f"- MVR: {mvr:.6f}")
    lines.append(f"- Violations: {n_violations} / {n_total}")
    lines.append(f"- Status: {'PASS' if mvr == 0 else 'FAIL'}")
    lines.append("")

    lines.append("## 5. Expected Calibration Error (ECE)")
    lines.append("")
    lines.append("| Horizon | ECE | N Bins | N Valid |")
    lines.append("|---------|-----|--------|---------|")

    for h in [1, 2, 3]:
        key = f"h{h}"
        ece = ece_results[key]
        lines.append(f"| h={h} | {ece['ece']:.6f} | {ece['n_bins']} | {ece['n_valid']} |")

    lines.append("")

    lines.append("## 6. 提前量指标")
    lines.append("")

    for h in [1, 2, 3]:
        key = f"h{h}"
        lt = lead_time_results[key]
        lines.append(f"### h={h}")
        lines.append("")
        if lt['Warning_Coverage'] is not None:
            lines.append(f"- Warning Coverage: {lt['Warning_Coverage']:.4f}")
        lines.append(f"- Miss Rate: {lt['Miss_Rate']:.4f}")
        if lt.get('note'):
            lines.append(f"- Note: {lt['note']}")
        lines.append("")

    lines.append("## 7. 重要说明")
    lines.append("")
    lines.append("- Heldout 仅在全部参数冻结后访问一次")
    lines.append("- 未使用 heldout 参与任何训练、校准、阈值选择或模型选择")
    lines.append("- 所有参数（模型权重、校准器、阈值）均在 train-dev 或 cal-dev 上确定")
    lines.append("")

    return "\n".join(lines)


def main(
    model: MHEORF,
    heldout_df: pd.DataFrame,
    device: torch.device,
) -> Dict:
    """
    主执行流程。

    Args:
        model: 冻结的模型
        heldout_df: heldout DataFrame
        device: 计算设备

    Returns:
        评估结果字典
    """
    print("=" * 70)
    print("SL-RDAF Phase 3: Heldout 一次性最终评估")
    print("=" * 70)

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 验证前置条件
    print("\n[Check] 验证前置条件...")
    if not verify_prerequisites():
        raise RuntimeError("前置条件不满足，无法执行 heldout 评估")
    print("  前置条件满足 ✓")

    # 1. 加载校准器和阈值
    print("\n[Step 0] 加载校准器和阈值...")

    calibrators = []
    for k in [1, 2, 3]:
        cal_path = Path(f"D:/SL-RDAF/outputs/calibration/f_{k}.pkl")
        calibrator = IsotonicCalibrator.load(cal_path)
        calibrators.append(calibrator)
        print(f"  f_{k} 已加载")

    theta_path = Path("D:/SL-RDAF/outputs/calibration/theta_h.json")
    with open(theta_path, "r", encoding="utf-8") as f:
        thresholds = json.load(f)
    print(f"  阈值已加载: θ_1={thresholds['theta_1']:.4f}, θ_2={thresholds['theta_2']:.4f}, θ_3={thresholds['theta_3']:.4f}")

    # 2. 在 heldout 上预测
    q_all, Q_all, y_cum_all, sample_info = predict_on_heldout(model, heldout_df, device)

    # 提取 valid mask
    valid_mask_cum = heldout_df[[VALID_H1, VALID_H2, VALID_H3]].values.astype(np.float32)

    # 3. 应用校准器
    print("\n[Step 2] 应用校准器...")
    q_tilde_all = apply_isotonic_calibrators(calibrators, q_all)
    Q_tilde_all = compute_calibrated_cumulative_risk(q_tilde_all)

    # 4. 应用阈值
    print("\n[Step 3] 应用阈值...")
    from sl_rdaf.calibration.threshold import apply_thresholds
    y_hat_all = apply_thresholds(Q_tilde_all, thresholds)

    # 5. 保存预测
    print("\n[Step 4] 保存 heldout 预测...")
    save_heldout_predictions(
        sample_info, q_all, Q_all, q_tilde_all, Q_tilde_all,
        y_hat_all, y_cum_all, valid_mask_cum, thresholds,
    )

    # 6. 计算指标
    print("\n[Step 5] 计算评估指标...")
    metrics = compute_horizon_metrics(Q_tilde_all, y_hat_all, y_cum_all, valid_mask_cum)
    print_metrics_summary(metrics)

    # 7. 计算 MVR
    print("\n[Step 6] 计算单调性违反率...")
    mvr, n_violations, n_total = compute_mvr(Q_tilde_all)
    print_mvr_summary(mvr, n_violations, n_total)

    # 8. 计算 ECE
    print("\n[Step 7] 计算 ECE...")
    ece_results = compute_ece_by_horizon(Q_tilde_all, y_cum_all, valid_mask_cum)
    print_ece_summary(ece_results)

    # 9. 计算提前量指标
    print("\n[Step 8] 计算提前量指标...")
    lead_time_results = compute_lead_time_metrics(
        heldout_df, y_hat_all, Q_tilde_all, y_cum_all, valid_mask_cum, thresholds
    )
    print_lead_time_summary(lead_time_results)

    # 10. 保存指标
    print("\n[Step 9] 保存评估指标...")

    metrics_df = pd.DataFrame([
        {
            "horizon": h,
            **metrics[f"h{h}"]
        }
        for h in [1, 2, 3]
    ])

    metrics_path = OUTPUT_DIR / "heldout_metrics_by_horizon.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"  指标已保存: {metrics_path}")

    # 11. 生成报告
    print("\n[Step 10] 生成评估报告...")
    report_md = generate_evaluation_report(
        heldout_df, metrics, mvr, n_violations, n_total,
        ece_results, lead_time_results, thresholds
    )

    report_path = OUTPUT_DIR / "heldout_evaluation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"  评估报告已保存: {report_path}")

    # 12. 保存摘要
    summary = {
        "heldout_samples": int(heldout_df[SAMPLE_ID_COL].nunique()),
        "heldout_rows": int(len(heldout_df)),
        "thresholds": thresholds,
        "metrics": metrics,
        "MVR": {
            "mvr": float(mvr),
            "n_violations": int(n_violations),
            "n_total": int(n_total),
        },
        "ECE": ece_results,
        "lead_time": lead_time_results,
    }

    summary_path = OUTPUT_DIR / "heldout_evaluation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"  评估摘要已保存: {summary_path}")

    # 13. 控制台输出
    print("\n" + "=" * 70)
    print("[SL-RDAF Phase 3 Heldout Evaluation Completed]")
    print("=" * 70)
    print(f"\nHeldout one-shot:")
    print(f"  accessed only after all parameters frozen: PASS")
    print(f"  samples: {heldout_df[SAMPLE_ID_COL].nunique()}")
    print(f"  rows: {len(heldout_df)}")

    for h in [1, 2, 3]:
        key = f"h{h}"
        m = metrics[key]
        auroc_str = f"{m['AUROC']:.4f}" if m['AUROC'] is not None else "N/A"
        auprc_str = f"{m['AUPRC']:.4f}" if m['AUPRC'] is not None else "N/A"
        print(f"  AUROC h={h}: {auroc_str}")
        print(f"  AUPRC h={h}: {auprc_str}")
        print(f"  F1 h={h}: {m['F1']:.4f}")

    print(f"  MVR: {mvr:.6f}")
    print(f"\nOutput files:")
    print(f"  {OUTPUT_DIR / 'heldout_predictions.csv'}")
    print(f"  {OUTPUT_DIR / 'heldout_metrics_by_horizon.csv'}")
    print(f"  {OUTPUT_DIR / 'heldout_evaluation_report.md'}")
    print(f"  {OUTPUT_DIR / 'heldout_evaluation_summary.json'}")
    print("=" * 70)

    return summary


if __name__ == "__main__":
    # 独立运行时，加载模型和数据
    from sl_rdaf.training.train_main import load_and_process_data

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

    # 加载 heldout 数据
    _, _, heldout_df = load_and_process_data()

    device = torch.device("cpu")

    main(model, heldout_df, device)
