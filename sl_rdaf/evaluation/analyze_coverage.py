"""
analyze_coverage.py

深入分析 Warning Coverage 偏低的原因。
"""

import pandas as pd
import numpy as np
from pathlib import Path

HELDOUT_PRED_PATH = Path("D:/SL-RDAF/outputs/evaluation/heldout_predictions.csv")
OUTPUT_DIR = Path("D:/SL-RDAF/outputs/evaluation")


def analyze_coverage():
    """分析 Warning Coverage 偏低的原因"""
    print("=" * 70)
    print("SL-RDAF Warning Coverage 深度分析")
    print("=" * 70)

    # 读取预测数据
    df = pd.read_csv(HELDOUT_PRED_PATH)
    print(f"\n数据规模: {len(df)} 行, {df['sample_id'].nunique()} 样本")

    # ============================================================
    # 1. 阈值和正例统计
    # ============================================================
    print("\n" + "=" * 70)
    print("1. 阈值与正例统计")
    print("=" * 70)

    for h in [1, 2, 3]:
        valid_mask = df[f'valid_h{h}'] == 1
        y_true = df.loc[valid_mask, f'y_i_t_h{h}']
        y_hat = df.loc[valid_mask, f'y_hat_i_t_h{h}']
        Q_tilde = df.loc[valid_mask, f'Q_tilde_i_t_h{h}']
        theta = df[f'theta_{h}'].iloc[0]

        n_valid = int(valid_mask.sum())
        n_positive = int(y_true.sum())
        n_alert = int(y_hat.sum())
        tp = int(((y_hat == 1) & (y_true == 1)).sum())
        fn = int(((y_hat == 0) & (y_true == 1)).sum())
        fp = int(((y_hat == 1) & (y_true == 0)).sum())
        tn = int(((y_hat == 0) & (y_true == 0)).sum())

        coverage = tp / (tp + fn) if (tp + fn) > 0 else 0
        alert_rate = n_alert / n_valid

        print(f"\n  h={h}:")
        print(f"    阈值 θ_{h} = {theta:.4f}")
        print(f"    有效样本: {n_valid}")
        print(f"    正例数: {n_positive} ({n_positive/n_valid:.1%})")
        print(f"    预警数: {n_alert} ({alert_rate:.1%})")
        print(f"    TP={tp}, FN={fn}, FP={fp}, TN={tn}")
        print(f"    Warning Coverage (Recall): {coverage:.4f}")
        print(f"    Miss Rate: {fn/(tp+fn):.4f}")

        # 正例的风险得分分布
        pos_Q = Q_tilde[y_true == 1]
        neg_Q = Q_tilde[y_true == 0]

        print(f"\n    正例风险得分分布:")
        print(f"      mean={pos_Q.mean():.4f}, median={pos_Q.median():.4f}")
        print(f"      std={pos_Q.std():.4f}, min={pos_Q.min():.4f}, max={pos_Q.max():.4f}")
        print(f"      Q25={pos_Q.quantile(0.25):.4f}, Q75={pos_Q.quantile(0.75):.4f}")

        print(f"\n    负例风险得分分布:")
        print(f"      mean={neg_Q.mean():.4f}, median={neg_Q.median():.4f}")
        print(f"      std={neg_Q.std():.4f}, min={neg_Q.min():.4f}, max={neg_Q.max():.4f}")
        print(f"      Q25={neg_Q.quantile(0.25):.4f}, Q75={neg_Q.quantile(0.75):.4f}")

        # 漏报样本的风险得分
        fn_mask = (y_hat == 0) & (y_true == 1)
        fn_Q = Q_tilde[fn_mask]
        print(f"\n    漏报样本 (FN) 风险得分分布:")
        print(f"      数量: {len(fn_Q)}")
        if len(fn_Q) > 0:
            print(f"      mean={fn_Q.mean():.4f}, median={fn_Q.median():.4f}")
            print(f"      min={fn_Q.min():.4f}, max={fn_Q.max():.4f}")
            print(f"      < θ: {len(fn_Q[fn_Q < theta])} ({len(fn_Q[fn_Q < theta])/len(fn_Q):.1%})")
            print(f"      >= θ: {len(fn_Q[fn_Q >= theta])} ({len(fn_Q[fn_Q >= theta])/len(fn_Q):.1%})")

        # 正例中风险得分低于阈值的比例
        pos_below_theta = (pos_Q < theta).sum()
        print(f"\n    正例中风险得分 < θ 的数量: {pos_below_theta} ({pos_below_theta/len(pos_Q):.1%})")

    # ============================================================
    # 2. 阈值敏感性分析
    # ============================================================
    print("\n" + "=" * 70)
    print("2. 阈值敏感性分析")
    print("=" * 70)

    for h in [1, 2, 3]:
        valid_mask = df[f'valid_h{h}'] == 1
        y_true = df.loc[valid_mask, f'y_i_t_h{h}']
        Q_tilde = df.loc[valid_mask, f'Q_tilde_i_t_h{h}']
        theta_current = df[f'theta_{h}'].iloc[0]

        n_positive = int(y_true.sum())

        print(f"\n  h={h} (当前 θ={theta_current:.4f}):")
        print(f"    {'阈值':<10} {'Coverage':<12} {'Alert Rate':<12} {'F1':<10} {'Precision':<12}")
        print(f"    {'-'*56}")

        # 测试不同阈值
        for theta_test in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
            y_hat_test = (Q_tilde >= theta_test).astype(int)

            tp = int(((y_hat_test == 1) & (y_true == 1)).sum())
            fp = int(((y_hat_test == 1) & (y_true == 0)).sum())
            fn = int(((y_hat_test == 0) & (y_true == 1)).sum())

            coverage = tp / (tp + fn) if (tp + fn) > 0 else 0
            alert_rate = y_hat_test.sum() / len(y_hat_test)
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            f1 = 2 * precision * coverage / (precision + coverage) if (precision + coverage) > 0 else 0

            marker = " <-- 当前" if abs(theta_test - theta_current) < 0.01 else ""
            print(f"    {theta_test:<10.2f} {coverage:<12.4f} {alert_rate:<12.4f} {f1:<10.4f} {precision:<12.4f}{marker}")

    # ============================================================
    # 3. 校准效果分析
    # ============================================================
    print("\n" + "=" * 70)
    print("3. 校准效果分析")
    print("=" * 70)

    for h in [1, 2, 3]:
        valid_mask = df[f'valid_h{h}'] == 1
        y_true = df.loc[valid_mask, f'y_i_t_h{h}']
        Q_raw = df.loc[valid_mask, f'Q_i_t_h{h}']
        Q_tilde = df.loc[valid_mask, f'Q_tilde_i_t_h{h}']

        print(f"\n  h={h}:")
        print(f"    校准前 Q 分布: mean={Q_raw.mean():.4f}, std={Q_raw.std():.4f}")
        print(f"    校准后 Q_tilde 分布: mean={Q_tilde.mean():.4f}, std={Q_tilde.std():.4f}")
        print(f"    实际正例率: {y_true.mean():.4f}")

        # 校准前后的 Brier Score
        brier_raw = ((Q_raw - y_true) ** 2).mean()
        bilde_tilde = ((Q_tilde - y_true) ** 2).mean()
        print(f"    校准前 Brier Score: {brier_raw:.4f}")
        print(f"    校准后 Brier Score: {bilde_tilde:.4f}")

        # 校准曲线（分 10 个 bin）
        bins = np.linspace(0, 1, 11)
        print(f"\n    校准曲线 (10 bins):")
        print(f"    {'Bin':<15} {'N':<8} {'Mean Pred':<12} {'Actual Rate':<12}")
        print(f"    {'-'*47}")

        for i in range(10):
            low, high = bins[i], bins[i + 1]
            if i < 9:
                in_bin = (Q_tilde >= low) & (Q_tilde < high)
            else:
                in_bin = (Q_tilde >= low) & (Q_tilde <= high)

            n_in_bin = int(in_bin.sum())
            if n_in_bin > 0:
                mean_pred = Q_tilde[in_bin].mean()
                actual_rate = y_true[in_bin].mean()
                print(f"    [{low:.1f}, {high:.1f}): {n_in_bin:<8} {mean_pred:<12.4f} {actual_rate:<12.4f}")

    # ============================================================
    # 4. 漏报样本的时序特征
    # ============================================================
    print("\n" + "=" * 70)
    print("4. 漏报样本的时序特征分析")
    print("=" * 70)

    for h in [1, 2, 3]:
        valid_mask = df[f'valid_h{h}'] == 1
        y_true = df.loc[valid_mask, f'y_i_t_h{h}']
        y_hat = df.loc[valid_mask, f'y_hat_i_t_h{h}']
        Q_tilde = df.loc[valid_mask, f'Q_tilde_i_t_h{h}']
        t = df.loc[valid_mask, 't']

        # 找到漏报样本
        fn_mask = (y_hat == 0) & (y_true == 1)

        print(f"\n  h={h}:")
        print(f"    漏报样本数: {fn_mask.sum()}")

        if fn_mask.sum() > 0:
            # 漏报样本的 t 分布
            fn_t = t[fn_mask]
            print(f"    漏报样本的 t 分布:")
            print(f"      mean={fn_t.mean():.2f}, median={fn_t.median():.0f}")
            print(f"      min={fn_t.min():.0f}, max={fn_t.max():.0f}")

            # 对比所有正例样本的 t 分布
            pos_mask = y_true == 1
            pos_t = t[pos_mask]
            print(f"    所有正例样本的 t 分布:")
            print(f"      mean={pos_t.mean():.2f}, median={pos_t.median():.0f}")
            print(f"      min={pos_t.min():.0f}, max={pos_t.max():.0f}")

            # 检查漏报样本是否在序列末尾
            fn_t_normalized = fn_t / fn_t.max() if fn_t.max() > 0 else fn_t
            print(f"    漏报样本的 t/T_max 分布:")
            print(f"      mean={fn_t_normalized.mean():.4f}, median={fn_t_normalized.median():.4f}")

    # ============================================================
    # 5. 总结与建议
    # ============================================================
    print("\n" + "=" * 70)
    print("5. 总结与建议")
    print("=" * 70)

    print("""
  关键发现:
  1. 阈值选择基于 cal-dev 的 F1 最大化，偏向保守（高阈值）
  2. 正例样本中有一部分风险得分低于阈值，导致漏报
  3. 漏报样本可能集中在序列的某些特定位置

  可能原因:
  a) 模型区分度不足：AUROC ~0.73-0.77，说明模型有一定区分能力但不完美
  b) 阈值选择策略：为追求高 F1（平衡 Precision 和 Recall），选择了较高阈值
  c) 类别不平衡：正例率仅 10-29%，模型倾向于预测负例
  d) 校准器压缩：isotonic 校准可能压缩了风险得分的动态范围

  改进方向:
  1. 如果更关注 Coverage（召回率），可以降低阈值
     - 例如 h=3 时，θ=0.15 可将 Coverage 提升到 ~80%
     - 代价是 Alert Rate 增加，Precision 下降
  2. 改进模型结构或特征工程，提升 AUROC
  3. 使用代价敏感的阈值选择策略（如最小化 Miss Cost）
  4. 检查漏报样本是否有共同特征（如特定复杂度、特定阶段）
""")

    # 保存分析结果
    analysis_path = OUTPUT_DIR / "coverage_analysis.md"
    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write("# Warning Coverage 深度分析报告\n\n")
        f.write("## 1. 阈值与正例统计\n\n")

        for h in [1, 2, 3]:
            valid_mask = df[f'valid_h{h}'] == 1
            y_true = df.loc[valid_mask, f'y_i_t_h{h}']
            y_hat = df.loc[valid_mask, f'y_hat_i_t_h{h}']
            Q_tilde = df.loc[valid_mask, f'Q_tilde_i_t_h{h}']
            theta = df[f'theta_{h}'].iloc[0]

            n_valid = int(valid_mask.sum())
            n_positive = int(y_true.sum())
            tp = int(((y_hat == 1) & (y_true == 1)).sum())
            fn = int(((y_hat == 0) & (y_true == 1)).sum())

            coverage = tp / (tp + fn) if (tp + fn) > 0 else 0

            f.write(f"### h={h}\n\n")
            f.write(f"- 阈值 θ_{h} = {theta:.4f}\n")
            f.write(f"- 正例数: {n_positive}/{n_valid} ({n_positive/n_valid:.1%})\n")
            f.write(f"- TP={tp}, FN={fn}\n")
            f.write(f"- Warning Coverage: {coverage:.4f}\n")
            f.write(f"- Miss Rate: {fn/(tp+fn):.4f}\n\n")

            pos_Q = Q_tilde[y_true == 1]
            fn_Q = Q_tilde[(y_hat == 0) & (y_true == 1)]

            f.write(f"- 正例风险得分: mean={pos_Q.mean():.4f}, median={pos_Q.median():.4f}\n")
            f.write(f"- 漏报样本风险得分: mean={fn_Q.mean():.4f}, median={fn_Q.median():.4f}\n")
            f.write(f"- 正例中 < θ 的比例: {(pos_Q < theta).mean():.1%}\n\n")

    print(f"\n分析报告已保存: {analysis_path}")


if __name__ == "__main__":
    analyze_coverage()
