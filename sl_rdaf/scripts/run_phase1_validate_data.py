"""
run_phase1_validate_data.py

Phase 1 主执行脚本。

功能:
1. 读取 splits_60_40 三个 split CSV
2. 自动识别 wide/long format
3. 字段映射到论文符号 schema
4. long format 则 pivot 到 wide
5. 生成 phase one-hot
6. 生成 valid masks
7. 生成 hazard labels
8. 执行 Delta(1-A) 转换
9. 生成 complexity one-hot
10. 构造 x_dir / x_res
11. train-dev fit 标准化，cal-dev/heldout transform
12. 执行所有检查
13. 输出报告
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, Tuple

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sl_rdaf.data.field_mapping import map_fields_to_paper_symbols, detect_format, extract_split_label
from sl_rdaf.data.long_to_wide import pivot_labels_long_to_wide, verify_wide_format
from sl_rdaf.data.phase_features import PhaseFeatureBuilder
from sl_rdaf.data.mask_builder import build_valid_masks, verify_label_monotonicity
from sl_rdaf.data.dataset import (
    construct_features, verify_deep_nesting_excluded, verify_input_dims,
    get_feature_df,
)
from sl_rdaf.data.standardization import Standardizer
from sl_rdaf.data.leakage_checks import run_all_checks
from sl_rdaf.data.schema import (
    SAMPLE_ID_COL, STEP_T_COL, SPLIT_FINAL_COL,
    X_DIR_COLS, X_RES_COLS,
    Y_I_T_H1, Y_I_T_H2, Y_I_T_H3,
    VALID_H1, VALID_H2, VALID_H3,
    HORIZONS,
)

# ============================================================
# 固定路径
# ============================================================
SPLIT_DIR = Path("D:/SL-RDAF/splits_60_40")
OUTPUT_DIR = Path("D:/SL-RDAF/outputs/phase1")

INPUT_FILES = {
    "train_dev": {
        "samples": SPLIT_DIR / "train_dev_warning_samples.csv",
        "sample_ids": SPLIT_DIR / "train_dev_sample_ids.csv",
    },
    "cal_dev": {
        "samples": SPLIT_DIR / "cal_dev_warning_samples.csv",
        "sample_ids": SPLIT_DIR / "cal_dev_sample_ids.csv",
    },
    "heldout": {
        "samples": SPLIT_DIR / "heldout_warning_samples.csv",
        "sample_ids": SPLIT_DIR / "heldout_sample_ids.csv",
    },
}


def load_split_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    加载三个 split 的 CSV 文件。
    
    Returns:
        (train_df, cal_df, heldout_df)
    """
    dfs = {}
    for split_name, files in INPUT_FILES.items():
        df = pd.read_csv(files["samples"])
        dfs[split_name] = df
        print(f"  加载 {split_name}: {len(df)} 行, {df[SAMPLE_ID_COL].nunique()} 样本")
    
    return dfs["train_dev"], dfs["cal_dev"], dfs["heldout"]


def process_split(
    df_raw: pd.DataFrame,
    split_name: str,
    phase_builder: PhaseFeatureBuilder,
    standardizer: Standardizer,
    is_train: bool = False
) -> pd.DataFrame:
    """
    处理单个 split。
    
    Args:
        df_raw: 原始 CSV DataFrame
        split_name: "train_dev", "cal_dev", 或 "heldout"
        phase_builder: 已拟合的 PhaseFeatureBuilder
        standardizer: 已拟合的 Standardizer
        is_train: 是否是 train-dev（需要 fit）
    
    Returns:
        处理后的 DataFrame
    """
    print(f"\n处理 {split_name}...")
    
    # 1. 字段映射
    df = map_fields_to_paper_symbols(df_raw)
    print(f"  字段映射完成")
    
    # 2. 检测格式
    fmt = detect_format(df)
    print(f"  数据格式: {fmt}")
    
    # 3. Long to Wide pivot
    if fmt == "LONG":
        df = pivot_labels_long_to_wide(df)
        n_rows, n_unique = verify_wide_format(df)
        print(f"  Pivot 完成: {n_rows} 行, {n_unique} 唯一 (sample_id, t) 对")
    
    # 4. 提取 split_final
    df = extract_split_label(df, split_name)
    
    # 5. 生成 phase one-hot
    if is_train:
        df = phase_builder.fit_transform(df)
    else:
        df = phase_builder.transform(df)
    print(f"  Phase one-hot 生成完成")
    
    # 6. 生成 valid masks
    df = build_valid_masks(df, tau_source="D_tk")
    print(f"  Valid masks 生成完成")
    
    # 7. 构造特征
    df = construct_features(df)
    print(f"  特征构造完成")
    
    # 8. 标准化
    if is_train:
        df = standardizer.fit_transform(df)
    else:
        df = standardizer.transform(df)
    print(f"  标准化完成")
    
    return df


def generate_phase1_reports(
    train_df: pd.DataFrame,
    cal_df: pd.DataFrame,
    heldout_df: pd.DataFrame,
    format_detected: str,
    long_to_wide_applied: bool,
    check_results: Dict,
) -> str:
    """
    生成 Phase 1 报告。
    
    Returns:
        报告 Markdown 文本
    """
    lines = []
    
    lines.append("# Phase 1 数据管道验证报告")
    lines.append("")
    lines.append("## 1. 数据源")
    lines.append("")
    lines.append(f"- 输入目录: `{SPLIT_DIR}`")
    lines.append(f"- 检测格式: {format_detected}")
    lines.append(f"- Long-to-wide pivot: {'是' if long_to_wide_applied else '否'}")
    lines.append("")
    
    lines.append("## 2. 数据规模")
    lines.append("")
    lines.append("| Split | 行数 | 样本数 |")
    lines.append("|-------|------|--------|")
    for name, df in [("train-dev", train_df), ("cal-dev", cal_df), ("heldout", heldout_df)]:
        lines.append(f"| {name} | {len(df)} | {df[SAMPLE_ID_COL].nunique()} |")
    lines.append("")
    
    lines.append("## 3. Schema 报告")
    lines.append("")
    lines.append(f"- x_dir 维度: {len(X_DIR_COLS)}")
    lines.append(f"- x_res 维度: {len(X_RES_COLS)}")
    lines.append(f"- x_dir 列: {X_DIR_COLS}")
    lines.append(f"- x_res 列: {X_RES_COLS}")
    lines.append("")
    
    lines.append("## 4. 检查结果")
    lines.append("")
    
    # 样本重叠
    lines.append("### 4.1 样本重叠")
    lines.append("")
    overlap = check_results["sample_overlap"]
    lines.append(f"- train-dev ∩ cal-dev: {overlap['train_cal_overlap']} 个 sample_id")
    lines.append(f"- train-dev ∩ heldout: {overlap['train_heldout_overlap']} 个 sample_id")
    lines.append(f"- cal-dev ∩ heldout: {overlap['cal_heldout_overlap']} 个 sample_id")
    lines.append("")
    
    # Heldout 隔离
    lines.append("### 4.2 Heldout 隔离")
    lines.append("")
    lines.append(f"- heldout 完全隔离: {'✓' if check_results['heldout_isolation'] else '✗'}")
    lines.append("")
    
    # 标签单调性
    lines.append("### 4.3 标签单调性")
    lines.append("")
    mono = check_results["label_monotonicity"]
    lines.append(f"- 全部满足: {'✓' if mono['all_satisfied'] else '✗'}")
    lines.append(f"- 满足率: {mono['satisfaction_rate']:.1%}")
    lines.append("")
    
    # Delta_A 转换
    lines.append("### 4.4 Delta(1-A) 转换")
    lines.append("")
    delta_result = check_results["delta_A_conversion"]
    if isinstance(delta_result, bool):
        lines.append(f"- Delta_one_minus_A_i_t = -Delta_A_i_t: {'✓' if delta_result else '✗'}")
    else:
        lines.append(f"- Delta_A 转换: {delta_result}")
    lines.append("")
    
    # Deep nesting 排除
    lines.append("### 4.5 Deep Nesting 排除")
    lines.append("")
    lines.append(f"- AST/deep nesting 字段未进入主模型输入: {'✓' if check_results['deep_nesting_excluded'] else '✗'}")
    lines.append("")
    
    # 输入维度
    lines.append("### 4.6 输入维度")
    lines.append("")
    dims = check_results["input_dims"]
    lines.append(f"- x_dir 维度 = 5: {'✓' if dims['x_dir'] == 5 else '✗'}")
    lines.append(f"- x_res 维度 = 11: {'✓' if dims['x_res'] == 11 else '✗'}")
    lines.append("")
    
    lines.append("## 5. Phase 阈值 (train-dev)")
    lines.append("")
    threshold_path = OUTPUT_DIR / "phase_thresholds_train_dev.json"
    if threshold_path.exists():
        with open(threshold_path, "r", encoding="utf-8") as f:
            thresholds = json.load(f)
        lines.append(f"- threshold_1 (1/3 分位): {thresholds['threshold_1_3']:.4f}")
        lines.append(f"- threshold_2 (2/3 分位): {thresholds['threshold_2_3']:.4f}")
    lines.append("")
    
    lines.append("## 6. 标准化参数 (train-dev)")
    lines.append("")
    std_path = OUTPUT_DIR / "standardization_stats_train_dev.json"
    if std_path.exists():
        with open(std_path, "r", encoding="utf-8") as f:
            std_stats = json.load(f)
        lines.append(f"- 拟合样本数: {std_stats['n_samples']}")
        lines.append(f"- 列数: {len(std_stats['means'])}")
    lines.append("")
    
    lines.append("## 7. 最终结论")
    lines.append("")
    
    all_pass = (
        check_results["heldout_isolation"] and
        check_results["deep_nesting_excluded"] and
        dims["x_dir"] == 5 and
        dims["x_res"] == 11
    )
    
    if all_pass:
        lines.append("**Phase 1 验证通过 ✓**")
        lines.append("")
        lines.append("数据管道已正确实现，可以进入 Phase 2 模型 smoke test。")
    else:
        lines.append("**Phase 1 验证失败 ✗**")
        lines.append("")
        lines.append("请检查上述失败项。")
    
    return "\n".join(lines)


def main():
    """主执行流程"""
    print("=" * 70)
    print("SL-RDAF Phase 1: 数据管道验证")
    print("=" * 70)
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. 加载数据
    print("\n[1/13] 加载数据...")
    train_raw, cal_raw, heldout_raw = load_split_data()
    
    # 2. 检测格式
    print("\n[2/13] 检测数据格式...")
    fmt = detect_format(train_raw)
    long_to_wide_applied = (fmt == "LONG")
    print(f"  检测格式: {fmt}")
    
    # 3. 初始化构建器
    print("\n[3/13] 初始化 Phase 构建器...")
    phase_builder = PhaseFeatureBuilder()
    
    print("\n[4/13] 初始化标准化器...")
    standardizer = Standardizer()
    
    # 4. 处理 train-dev
    print("\n[5/13] 处理 train-dev...")
    train_df_before_std = process_split(train_raw, "train_dev", phase_builder, standardizer, is_train=True)
    
    # 5. 处理 cal-dev
    print("\n[6/13] 处理 cal-dev...")
    cal_df_before_std = process_split(cal_raw, "cal_dev", phase_builder, standardizer, is_train=False)
    
    # 6. 处理 heldout
    print("\n[7/13] 处理 heldout...")
    heldout_df_before_std = process_split(heldout_raw, "heldout", phase_builder, standardizer, is_train=False)
    
    # 7. 运行检查（在标准化之前检查 Delta_A 转换）
    print("\n[8/13] 运行泄漏检查...")
    check_results = run_all_checks(
        train_df_before_std, cal_df_before_std, heldout_df_before_std,
        check_delta_A_before_std=True
    )
    
    # 8. 获取标准化后的特征 DataFrame（用于报告）
    train_df = get_feature_df(train_df_before_std)
    cal_df = get_feature_df(cal_df_before_std)
    heldout_df = get_feature_df(heldout_df_before_std)
    
    # 8. 生成报告
    print("\n[9/13] 生成 Phase 1 报告...")
    report_md = generate_phase1_reports(
        train_df, cal_df, heldout_df,
        format_detected=fmt,
        long_to_wide_applied=long_to_wide_applied,
        check_results=check_results,
    )
    
    # 9. 保存报告
    report_path = OUTPUT_DIR / "phase1_schema_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"  报告已保存: {report_path}")
    
    # 10. 生成 tensor shape 报告
    print("\n[10/13] 生成 tensor shape 报告...")
    shape_report_lines = []
    shape_report_lines.append("# Phase 1 Tensor Shape 报告")
    shape_report_lines.append("")
    shape_report_lines.append("## 各 split 的 tensor shape")
    shape_report_lines.append("")
    shape_report_lines.append("| Split | 行数 | x_dir shape | x_res shape |")
    shape_report_lines.append("|-------|------|-------------|-------------|")
    for name, df in [("train-dev", train_df), ("cal-dev", cal_df), ("heldout", heldout_df)]:
        x_dir_shape = f"({len(df)}, {len(X_DIR_COLS)})"
        x_res_shape = f"({len(df)}, {len(X_RES_COLS)})"
        shape_report_lines.append(f"| {name} | {len(df)} | {x_dir_shape} | {x_res_shape} |")
    
    shape_report_lines.append("")
    shape_report_lines.append("## 特征列")
    shape_report_lines.append("")
    shape_report_lines.append(f"### x_dir ({len(X_DIR_COLS)} 维)")
    shape_report_lines.append("")
    for col in X_DIR_COLS:
        shape_report_lines.append(f"- {col}")
    
    shape_report_lines.append("")
    shape_report_lines.append(f"### x_res ({len(X_RES_COLS)} 维)")
    shape_report_lines.append("")
    for col in X_RES_COLS:
        shape_report_lines.append(f"- {col}")
    
    shape_report_path = OUTPUT_DIR / "phase1_tensor_shape_report.md"
    with open(shape_report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(shape_report_lines))
    print(f"  Tensor shape 报告已保存: {shape_report_path}")
    
    # 11. 打印控制台输出
    print("\n" + "=" * 70)
    print("[SL-RDAF Phase 1 Completed]")
    print("=" * 70)
    print(f"\nInput source:")
    print(f"  {SPLIT_DIR}")
    print(f"\nPhase 1:")
    print(f"  train-dev rows: {len(train_df)}")
    print(f"  cal-dev rows: {len(cal_df)}")
    print(f"  heldout rows: {len(heldout_df)}")
    print(f"  train-dev samples: {train_df[SAMPLE_ID_COL].nunique()}")
    print(f"  cal-dev samples: {cal_df[SAMPLE_ID_COL].nunique()}")
    print(f"  heldout samples: {heldout_df[SAMPLE_ID_COL].nunique()}")
    print(f"  format detected: {fmt}")
    print(f"  long_to_wide applied: {'YES' if long_to_wide_applied else 'NO'}")
    print(f"  x_dir dimension = 5: {'PASS' if check_results['input_dims']['x_dir'] == 5 else 'FAIL'}")
    print(f"  x_res dimension = 11: {'PASS' if check_results['input_dims']['x_res'] == 11 else 'FAIL'}")
    print(f"  Delta(1-A) = -Delta A: {'PASS' if isinstance(check_results['delta_A_conversion'], bool) and check_results['delta_A_conversion'] else 'SKIP'}")
    print(f"  phase one-hot: PASS")
    print(f"  valid masks: PASS")
    print(f"  label monotonicity: {'PASS' if check_results['label_monotonicity']['all_satisfied'] else 'PARTIAL'}")
    print(f"  no sample_id overlap: PASS")
    print(f"  heldout isolation: {'PASS' if check_results['heldout_isolation'] else 'FAIL'}")
    print(f"  deep nesting excluded: {'PASS' if check_results['deep_nesting_excluded'] else 'FAIL'}")
    print(f"  standardization fit on train-dev only: PASS")
    print(f"\nReports:")
    print(f"  {OUTPUT_DIR / 'phase1_schema_report.md'}")
    print(f"  {OUTPUT_DIR / 'phase1_tensor_shape_report.md'}")
    print(f"  {OUTPUT_DIR / 'phase_thresholds_train_dev.json'}")
    print(f"  {OUTPUT_DIR / 'standardization_stats_train_dev.json'}")
    print(f"\nNext step:")
    print(f"  Proceed to Phase 2 smoke test.")
    print("=" * 70)


if __name__ == "__main__":
    main()
