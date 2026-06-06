"""
run_phase3_train_calibrate.py

SL-RDAF Phase 3 主执行脚本。

完整流程:
1. train-dev 训练模型参数 Θ
2. cal-dev 拟合 isotonic 校准器 f_k
3. cal-dev 冻结预警阈值 θ_h
4. heldout 一次性最终评估

严禁:
- 使用 heldout 参与任何训练、校准、阈值选择
- 使用 cal-dev 进行模型参数更新
- 执行消融实验
- 调参
"""

import torch
import numpy as np
import pandas as pd
import json
from pathlib import Path
from typing import Dict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sl_rdaf.model.sl_rdaf import MHEORF
from sl_rdaf.training.seed import set_global_seed
from sl_rdaf.training.train_main import load_and_process_data, build_dataloader
from sl_rdaf.training.class_weights import compute_class_weights, print_class_weights_summary
from sl_rdaf.training.trainer import MHEORFTrainer
from sl_rdaf.training.checkpointing import save_checkpoint
from sl_rdaf.calibration.calibrate_main import (
    predict_on_cal_dev,
    save_uncalibrated_predictions,
    fit_isotonic_calibrators,
    apply_isotonic_calibrators,
    compute_calibrated_cumulative_risk,
    save_calibrated_predictions,
    verify_monotonicity,
    search_all_thresholds,
    generate_calibration_report,
)
from sl_rdaf.calibration.threshold import apply_thresholds
from sl_rdaf.evaluation.evaluate_main import (
    verify_prerequisites,
    predict_on_heldout,
    save_heldout_predictions,
    compute_horizon_metrics,
    print_metrics_summary,
    compute_mvr,
    print_mvr_summary,
    compute_ece_by_horizon,
    print_ece_summary,
    compute_lead_time_metrics,
    print_lead_time_summary,
    generate_evaluation_report,
)
from sl_rdaf.data.schema import (
    SAMPLE_ID_COL,
    VALID_H1, VALID_H2, VALID_H3,
    VALID_HAZ_K1, VALID_HAZ_K2, VALID_HAZ_K3,
)

# ============================================================
# 固定路径
# ============================================================
OUTPUT_DIR_TRAINING = Path("D:/SL-RDAF/outputs/training")
OUTPUT_DIR_CALIBRATION = Path("D:/SL-RDAF/outputs/calibration")
OUTPUT_DIR_EVALUATION = Path("D:/SL-RDAF/outputs/evaluation")


def generate_phase3_summary(
    trainer: MHEORFTrainer,
    train_df: pd.DataFrame,
    cal_df: pd.DataFrame,
    heldout_df: pd.DataFrame,
    calibrator_stats: Dict,
    threshold_stats: Dict,
    thresholds: Dict,
    metrics: Dict,
    mvr: float,
    ece_results: Dict,
    lead_time_results: Dict,
) -> str:
    """
    生成 Phase 3 最终摘要。

    Returns:
        摘要文本
    """
    lines = []

    lines.append("[SL-RDAF Phase 3 Main Experiment Completed]")
    lines.append("")
    lines.append("Input source:")
    lines.append("  D:\\SL-RDAF\\outputs\\splits_60_40\\")
    lines.append("")
    lines.append("Frozen configuration:")
    lines.append(f"  seed: 20260528")
    lines.append(f"  optimizer: AdamW")
    lines.append(f"  learning_rate: {trainer.learning_rate}")
    lines.append(f"  weight_decay: {trainer.weight_decay}")
    lines.append(f"  lambda_haz: {trainer.lambda_haz}")
    lines.append(f"  max_epochs: {trainer.max_epochs}")
    lines.append(f"  batch_size: {trainer.batch_size}")
    lines.append(f"  early_stopping: false")
    lines.append("")
    lines.append("Train-dev:")
    lines.append(f"  samples: {train_df[SAMPLE_ID_COL].nunique()}")
    lines.append(f"  rows after phase1 wide format: {len(train_df)}")
    lines.append(f"  final train loss: {trainer.history['loss_total'][-1]:.6f}")
    lines.append(f"  model parameters: {sum(p.numel() for p in trainer.model.parameters()):,}")
    lines.append("")
    lines.append("Cal-dev:")
    lines.append(f"  samples: {cal_df[SAMPLE_ID_COL].nunique()}")
    lines.append(f"  f_1 fitted: {'PASS' if calibrator_stats['f_1']['fitted'] else 'FAIL'}")
    lines.append(f"  f_2 fitted: {'PASS' if calibrator_stats['f_2']['fitted'] else 'FAIL'}")
    lines.append(f"  f_3 fitted: {'PASS' if calibrator_stats['f_3']['fitted'] else 'FAIL'}")
    lines.append(f"  theta_1: {thresholds['theta_1']:.4f}")
    lines.append(f"  theta_2: {thresholds['theta_2']:.4f}")
    lines.append(f"  theta_3: {thresholds['theta_3']:.4f}")
    lines.append(f"  cal-dev h=1 positives: {int((cal_df['y_i_t_h1'] == 1).sum())}")
    lines.append("")
    lines.append("Heldout one-shot:")
    lines.append(f"  accessed only after all parameters frozen: PASS")
    lines.append(f"  samples: {heldout_df[SAMPLE_ID_COL].nunique()}")

    for h in [1, 2, 3]:
        key = f"h{h}"
        m = metrics[key]
        auroc_str = f"{m['AUROC']:.4f}" if m['AUROC'] is not None else "N/A"
        auprc_str = f"{m['AUPRC']:.4f}" if m['AUPRC'] is not None else "N/A"
        lines.append(f"  AUROC h{h}/h{h}/h{h}: {auroc_str}")
        lines.append(f"  AUPRC h{h}/h{h}/h{h}: {auprc_str}")
        lines.append(f"  F1 h{h}/h{h}/h{h}: {m['F1']:.4f}")

    lines.append(f"  MVR: {mvr:.6f}")
    lines.append("")
    lines.append("Output files:")
    lines.append(f"  D:\\SL-RDAF\\outputs\\training\\model_final.pt")
    lines.append(f"  D:\\SL-RDAF\\outputs\\training\\training_history.json")
    lines.append(f"  D:\\SL-RDAF\\outputs\\training\\training_report.md")
    lines.append(f"  D:\\SL-RDAF\\outputs\\calibration\\f_1.pkl")
    lines.append(f"  D:\\SL-RDAF\\outputs\\calibration\\f_2.pkl")
    lines.append(f"  D:\\SL-RDAF\\outputs\\calibration\\f_3.pkl")
    lines.append(f"  D:\\SL-RDAF\\outputs\\calibration\\theta_h.json")
    lines.append(f"  D:\\SL-RDAF\\outputs\\calibration\\calibration_report.md")
    lines.append(f"  D:\\SL-RDAF\\outputs\\evaluation\\heldout_predictions.csv")
    lines.append(f"  D:\\SL-RDAF\\outputs\\evaluation\\heldout_metrics_by_horizon.csv")
    lines.append(f"  D:\\SL-RDAF\\outputs\\evaluation\\heldout_evaluation_report.md")
    lines.append("")
    lines.append("Next step:")
    lines.append("  Do not run ablations yet. Send heldout_metrics_by_horizon.csv and heldout_evaluation_report.md for review before entering §4.4.")
    lines.append("")

    return "\n".join(lines)


def main():
    """主执行流程"""
    print("=" * 70)
    print("SL-RDAF Phase 3: 训练 + cal-dev 校准 + heldout 一次性评估")
    print("=" * 70)

    # 创建输出目录
    OUTPUT_DIR_TRAINING.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR_CALIBRATION.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR_EVALUATION.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # Step 0: 设置随机种子
    # ============================================================
    print("\n[Step 0] 设置随机种子...")
    set_global_seed(20260528)

    # ============================================================
    # Step 1: 加载 Phase 1 数据
    # ============================================================
    print("\n[Step 1] 加载 Phase 1 数据...")
    train_df, cal_df, heldout_df = load_and_process_data()

    # ============================================================
    # Step 2: 计算 train-dev 类别权重
    # ============================================================
    print("\n[Step 2] 计算 train-dev 类别权重...")
    class_weights_results = compute_class_weights(train_df)
    print_class_weights_summary(class_weights_results)

    # ============================================================
    # Step 3: 构建 DataLoader
    # ============================================================
    print("\n[Step 3] 构建 DataLoader...")
    train_dataloader = build_dataloader(train_df, batch_size=32, shuffle=True)
    print(f"  train-dev dataloader: {len(train_dataloader)} batches")

    # ============================================================
    # Step 4: 初始化模型
    # ============================================================
    print("\n[Step 4] 初始化模型...")
    model = MHEORF(
        x_dir_dim=5,
        x_res_dim=11,
        state_dim=8,
        n_horizons=3,
        activation="tanh"
    )
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  模型参数量: {n_params:,}")

    # ============================================================
    # Step 5: 检测设备
    # ============================================================
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n[Step 5] 设备: {device}")

    # ============================================================
    # Step 6: 训练模型（只使用 train-dev）
    # ============================================================
    print("\n[Step 6] 训练模型（只使用 train-dev）...")
    trainer = MHEORFTrainer(
        model=model,
        device=device,
        learning_rate=0.001,
        weight_decay=0.0001,
        lambda_haz=1.0,
        max_epochs=200,
        batch_size=32,
        gradient_clip_norm=5.0,
        class_weights=None,
        output_dir=OUTPUT_DIR_TRAINING,
    )

    history = trainer.fit(train_dataloader)

    # 保存训练产物
    print("\n[Step 7] 保存训练产物...")
    trainer.save_outputs()
    trainer.plot_loss_curve()

    # 生成训练报告
    from sl_rdaf.training.train_main import generate_training_report
    report_md = generate_training_report(trainer, train_df, class_weights_results)
    report_path = OUTPUT_DIR_TRAINING / "training_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"  训练报告已保存: {report_path}")

    # ============================================================
    # Step 8: cal-dev 校准（冻结模型参数）
    # ============================================================
    print("\n" + "=" * 70)
    print("[Step 8] cal-dev 校准（冻结模型参数）")
    print("=" * 70)

    # 冻结模型参数
    for param in trainer.model.parameters():
        param.requires_grad = False

    trainer.model.eval()

    # 8.1 在 cal-dev 上预测
    q_all, Q_all, y_haz_all, y_cum_all, sample_info = predict_on_cal_dev(
        trainer.model, cal_df, device
    )

    # 提取 valid masks
    valid_mask_haz = cal_df[[VALID_HAZ_K1, VALID_HAZ_K2, VALID_HAZ_K3]].values.astype(np.float32)
    valid_mask_cum = cal_df[[VALID_H1, VALID_H2, VALID_H3]].values.astype(np.float32)

    # 8.2 保存未校准预测
    save_uncalibrated_predictions(
        sample_info, q_all, Q_all, y_haz_all, y_cum_all,
        valid_mask_haz, valid_mask_cum, OUTPUT_DIR_CALIBRATION
    )

    # 8.3 拟合 isotonic 校准器
    print("\n[Step 8.3] 拟合 isotonic 校准器...")
    calibrators, calibrator_stats = fit_isotonic_calibrators(
        q_all, y_haz_all, valid_mask_haz, OUTPUT_DIR_CALIBRATION
    )

    # 8.4 应用校准器
    print("\n[Step 8.4] 应用校准器...")
    q_tilde_all = apply_isotonic_calibrators(calibrators, q_all)
    Q_tilde_all = compute_calibrated_cumulative_risk(q_tilde_all)

    # 验证单调性
    monotonicity_pass = verify_monotonicity(Q_tilde_all)
    print(f"  单调性验证: {'PASS' if monotonicity_pass else 'FAIL'}")

    # 8.5 保存校准后预测
    save_calibrated_predictions(sample_info, q_tilde_all, Q_tilde_all, OUTPUT_DIR_CALIBRATION)

    # 8.6 搜索阈值
    print("\n[Step 8.6] 搜索预警阈值...")
    thresholds, threshold_stats = search_all_thresholds(
        Q_tilde_all, y_cum_all, valid_mask_cum, OUTPUT_DIR_CALIBRATION
    )

    # 8.7 生成校准报告
    print("\n[Step 8.7] 生成校准报告...")
    from sl_rdaf.calibration.calibrate_main import generate_calibration_report
    cal_report_md = generate_calibration_report(
        cal_df, calibrator_stats, threshold_stats, thresholds, monotonicity_pass
    )
    cal_report_path = OUTPUT_DIR_CALIBRATION / "calibration_report.md"
    with open(cal_report_path, "w", encoding="utf-8") as f:
        f.write(cal_report_md)
    print(f"  校准报告已保存: {cal_report_path}")

    # 保存校准摘要
    cal_summary = {
        "cal_dev_samples": int(cal_df[SAMPLE_ID_COL].nunique()),
        "cal_dev_rows": int(len(cal_df)),
        "calibrator_stats": calibrator_stats,
        "thresholds": thresholds,
        "threshold_stats": threshold_stats,
        "monotonicity_pass": bool(monotonicity_pass),
    }
    cal_summary_path = OUTPUT_DIR_CALIBRATION / "calibration_summary.json"
    with open(cal_summary_path, "w", encoding="utf-8") as f:
        json.dump(cal_summary, f, indent=2, ensure_ascii=False)
    print(f"  校准摘要已保存: {cal_summary_path}")

    # ============================================================
    # Step 9: heldout 一次性最终评估
    # ============================================================
    print("\n" + "=" * 70)
    print("[Step 9] heldout 一次性最终评估")
    print("=" * 70)

    # 验证前置条件
    print("\n[Check] 验证前置条件...")
    if not verify_prerequisites():
        raise RuntimeError("前置条件不满足，无法执行 heldout 评估")
    print("  前置条件满足 [PASS]")

    # 加载校准器
    from sl_rdaf.calibration.isotonic import IsotonicCalibrator
    calibrators_loaded = []
    for k in [1, 2, 3]:
        cal_path = Path(f"D:/SL-RDAF/outputs/calibration/f_{k}.pkl")
        calibrator = IsotonicCalibrator.load(cal_path)
        calibrators_loaded.append(calibrator)

    # 在 heldout 上预测
    q_ho, Q_ho, y_cum_ho, sample_info_ho = predict_on_heldout(
        trainer.model, heldout_df, device
    )

    # 提取 valid mask
    valid_mask_cum_ho = heldout_df[[VALID_H1, VALID_H2, VALID_H3]].values.astype(np.float32)

    # 应用校准器
    q_tilde_ho = apply_isotonic_calibrators(calibrators_loaded, q_ho)
    Q_tilde_ho = compute_calibrated_cumulative_risk(q_tilde_ho)

    # 应用阈值
    y_hat_ho = apply_thresholds(Q_tilde_ho, thresholds)

    # 保存预测
    save_heldout_predictions(
        sample_info_ho, q_ho, Q_ho, q_tilde_ho, Q_tilde_ho,
        y_hat_ho, y_cum_ho, valid_mask_cum_ho, thresholds,
    )

    # 计算指标
    metrics = compute_horizon_metrics(Q_tilde_ho, y_hat_ho, y_cum_ho, valid_mask_cum_ho)
    print_metrics_summary(metrics)

    # 计算 MVR
    mvr, n_violations, n_total = compute_mvr(Q_tilde_ho)
    print_mvr_summary(mvr, n_violations, n_total)

    # 计算 ECE
    ece_results = compute_ece_by_horizon(Q_tilde_ho, y_cum_ho, valid_mask_cum_ho)
    print_ece_summary(ece_results)

    # 计算提前量指标
    lead_time_results = compute_lead_time_metrics(
        heldout_df, y_hat_ho, Q_tilde_ho, y_cum_ho, valid_mask_cum_ho, thresholds
    )
    print_lead_time_summary(lead_time_results)

    # 保存指标
    import pandas as pd
    metrics_df = pd.DataFrame([
        {
            "horizon": h,
            **metrics[f"h{h}"]
        }
        for h in [1, 2, 3]
    ])
    metrics_path = OUTPUT_DIR_EVALUATION / "heldout_metrics_by_horizon.csv"
    metrics_df.to_csv(metrics_path, index=False)
    print(f"\n  指标已保存: {metrics_path}")

    # 生成评估报告
    eval_report_md = generate_evaluation_report(
        heldout_df, metrics, mvr, n_violations, n_total,
        ece_results, lead_time_results, thresholds
    )
    eval_report_path = OUTPUT_DIR_EVALUATION / "heldout_evaluation_report.md"
    with open(eval_report_path, "w", encoding="utf-8") as f:
        f.write(eval_report_md)
    print(f"  评估报告已保存: {eval_report_path}")

    # 保存评估摘要
    eval_summary = {
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
    eval_summary_path = OUTPUT_DIR_EVALUATION / "heldout_evaluation_summary.json"
    with open(eval_summary_path, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2, ensure_ascii=False)
    print(f"  评估摘要已保存: {eval_summary_path}")

    # ============================================================
    # 最终控制台输出
    # ============================================================
    print("\n" + "=" * 70)
    summary = generate_phase3_summary(
        trainer, train_df, cal_df, heldout_df,
        calibrator_stats, threshold_stats, thresholds,
        metrics, mvr, ece_results, lead_time_results,
    )
    print(summary)
    print("=" * 70)


if __name__ == "__main__":
    main()
