"""
train_main.py

训练主流程。

加载 Phase 1 数据，训练 SL-RDAF 模型，保存训练产物。
"""

import pandas as pd
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset
from pathlib import Path
from typing import Tuple, Dict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sl_rdaf.model.sl_rdaf import MHEORF
from sl_rdaf.training.seed import set_global_seed
from sl_rdaf.training.class_weights import compute_class_weights, print_class_weights_summary
from sl_rdaf.training.trainer import MHEORFTrainer
from sl_rdaf.data.schema import (
    SAMPLE_ID_COL, STEP_T_COL,
    X_DIR_COLS, X_RES_COLS,
    Y_I_T_H1, Y_I_T_H2, Y_I_T_H3,
    Y_HAZ_I_T_K1, Y_HAZ_I_T_K2, Y_HAZ_I_T_K3,
    VALID_H1, VALID_H2, VALID_H3,
    VALID_HAZ_K1, VALID_HAZ_K2, VALID_HAZ_K3,
)
from sl_rdaf.data.field_mapping import map_fields_to_paper_symbols, detect_format, extract_split_label
from sl_rdaf.data.long_to_wide import pivot_labels_long_to_wide, verify_wide_format
from sl_rdaf.data.phase_features import PhaseFeatureBuilder
from sl_rdaf.data.mask_builder import build_valid_masks
from sl_rdaf.data.dataset import construct_features, get_feature_df
from sl_rdaf.data.standardization import Standardizer

# ============================================================
# 固定路径
# ============================================================
SPLIT_DIR = Path("D:/SL-RDAF/splits_60_40")
OUTPUT_DIR = Path("D:/SL-RDAF/outputs/training")

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


def load_and_process_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    加载并处理三个 split 的数据。

    Returns:
        (train_df, cal_df, heldout_df)
    """
    print("\n[Step 1] 加载 Phase 1 数据...")

    # 加载原始数据
    train_raw = pd.read_csv(INPUT_FILES["train_dev"]["samples"])
    cal_raw = pd.read_csv(INPUT_FILES["cal_dev"]["samples"])
    heldout_raw = pd.read_csv(INPUT_FILES["heldout"]["samples"])

    print(f"  train-dev: {len(train_raw)} 行, {train_raw[SAMPLE_ID_COL].nunique()} 样本")
    print(f"  cal-dev: {len(cal_raw)} 行, {cal_raw[SAMPLE_ID_COL].nunique()} 样本")
    print(f"  heldout: {len(heldout_raw)} 行, {heldout_raw[SAMPLE_ID_COL].nunique()} 样本")

    # 检测格式
    fmt = detect_format(train_raw)
    print(f"  数据格式: {fmt}")

    # 初始化构建器
    phase_builder = PhaseFeatureBuilder()
    standardizer = Standardizer()

    def process_split(df_raw, split_name, is_train=False):
        # 字段映射
        df = map_fields_to_paper_symbols(df_raw)
        
        # Long to Wide
        if fmt == "LONG":
            df = pivot_labels_long_to_wide(df)
            verify_wide_format(df)
        
        # 提取 split_final
        df = extract_split_label(df, split_name)
        
        # Phase one-hot
        if is_train:
            df = phase_builder.fit_transform(df)
        else:
            df = phase_builder.transform(df)
        
        # Valid masks
        df = build_valid_masks(df, tau_source="D_tk")
        
        # 构造特征
        df = construct_features(df)
        
        # 标准化
        if is_train:
            df = standardizer.fit_transform(df)
        else:
            df = standardizer.transform(df)
        
        return df

    # 处理 train-dev
    train_df = process_split(train_raw, "train_dev", is_train=True)
    
    # 处理 cal-dev
    cal_df = process_split(cal_raw, "cal_dev", is_train=False)
    
    # 处理 heldout
    heldout_df = process_split(heldout_raw, "heldout", is_train=False)

    print(f"  train-dev: {len(train_df)} 行, {train_df[SAMPLE_ID_COL].nunique()} 样本")
    print(f"  cal-dev: {len(cal_df)} 行, {cal_df[SAMPLE_ID_COL].nunique()} 样本")
    print(f"  heldout: {len(heldout_df)} 行, {heldout_df[SAMPLE_ID_COL].nunique()} 样本")

    return train_df, cal_df, heldout_df


def build_dataloader(
    df: pd.DataFrame,
    batch_size: int = 32,
    shuffle: bool = True,
) -> DataLoader:
    """
    从 DataFrame 构建 DataLoader。

    Args:
        df: 处理后的 DataFrame
        batch_size: batch size
        shuffle: 是否打乱

    Returns:
        DataLoader
    """
    # 提取特征和标签
    feature_cols = X_DIR_COLS + X_RES_COLS
    y_cum_cols = [Y_I_T_H1, Y_I_T_H2, Y_I_T_H3]
    y_haz_cols = [Y_HAZ_I_T_K1, Y_HAZ_I_T_K2, Y_HAZ_I_T_K3]
    valid_cum_cols = [VALID_H1, VALID_H2, VALID_H3]
    valid_haz_cols = [VALID_HAZ_K1, VALID_HAZ_K2, VALID_HAZ_K3]

    # 按 sample_id 分组，构建序列
    samples = []
    for sample_id, group in df.groupby(SAMPLE_ID_COL):
        # 按 t 排序
        group = group.sort_values(STEP_T_COL)
        
        x_dir = group[X_DIR_COLS].values.astype(np.float32)
        x_res = group[X_RES_COLS].values.astype(np.float32)
        y_cum = group[y_cum_cols].values.astype(np.float32)
        y_haz = group[y_haz_cols].values.astype(np.float32)
        valid_cum = group[valid_cum_cols].values.astype(np.float32)
        valid_haz = group[valid_haz_cols].values.astype(np.float32)

        samples.append((x_dir, x_res, y_cum, y_haz, valid_cum, valid_haz))

    # 填充到相同长度
    max_len = max(s[0].shape[0] for s in samples)

    x_dir_batch = np.zeros((len(samples), max_len, len(X_DIR_COLS)), dtype=np.float32)
    x_res_batch = np.zeros((len(samples), max_len, len(X_RES_COLS)), dtype=np.float32)
    y_cum_batch = np.zeros((len(samples), max_len, 3), dtype=np.float32)
    y_haz_batch = np.zeros((len(samples), max_len, 3), dtype=np.float32)
    valid_cum_batch = np.zeros((len(samples), max_len, 3), dtype=np.float32)
    valid_haz_batch = np.zeros((len(samples), max_len, 3), dtype=np.float32)

    for i, (x_dir, x_res, y_cum, y_haz, valid_cum, valid_haz) in enumerate(samples):
        T = x_dir.shape[0]
        x_dir_batch[i, :T, :] = x_dir
        x_res_batch[i, :T, :] = x_res
        
        # 填充 y_cum，NaN 填充为 0
        y_cum_clean = np.nan_to_num(y_cum, nan=0.0)
        y_cum_batch[i, :T, :] = y_cum_clean
        
        # 填充 y_haz，NaN 填充为 0
        y_haz_clean = np.nan_to_num(y_haz, nan=0.0)
        y_haz_batch[i, :T, :] = y_haz_clean
        
        valid_cum_batch[i, :T, :] = valid_cum
        valid_haz_batch[i, :T, :] = valid_haz

    # 转换为 Tensor
    x_dir_tensor = torch.from_numpy(x_dir_batch)
    x_res_tensor = torch.from_numpy(x_res_batch)
    y_cum_tensor = torch.from_numpy(y_cum_batch)
    y_haz_tensor = torch.from_numpy(y_haz_batch)
    valid_cum_tensor = torch.from_numpy(valid_cum_batch)
    valid_haz_tensor = torch.from_numpy(valid_haz_batch)

    dataset = TensorDataset(
        x_dir_tensor, x_res_tensor, y_cum_tensor, y_haz_tensor, valid_cum_tensor, valid_haz_tensor
    )

    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)

    return dataloader


def generate_training_report(
    trainer: MHEORFTrainer,
    train_df: pd.DataFrame,
    class_weights_results: Dict,
) -> str:
    """
    生成训练报告。

    Returns:
        Markdown 报告文本
    """
    lines = []

    lines.append("# Phase 3 训练报告")
    lines.append("")
    lines.append("## 1. 训练配置")
    lines.append("")
    lines.append(f"- 随机种子: 20260528")
    lines.append(f"- 优化器: AdamW")
    lines.append(f"- 学习率: {trainer.learning_rate}")
    lines.append(f"- 权重衰减: {trainer.weight_decay}")
    lines.append(f"- Lambda haz: {trainer.lambda_haz}")
    lines.append(f"- Max epochs: {trainer.max_epochs}")
    lines.append(f"- Batch size: {trainer.batch_size}")
    lines.append(f"- Early stopping: false")
    lines.append(f"- Gradient clip norm: {trainer.gradient_clip_norm}")
    lines.append(f"- 设备: {trainer.device}")
    lines.append("")

    lines.append("## 2. 数据规模")
    lines.append("")
    lines.append(f"- Train-dev 样本数: {train_df[SAMPLE_ID_COL].nunique()}")
    lines.append(f"- Train-dev 行数: {len(train_df)}")
    lines.append("")

    lines.append("## 3. 类别权重 (train-dev)")
    lines.append("")
    print_class_weights_summary(class_weights_results)
    for key, value in class_weights_results.items():
        if isinstance(value, dict):
            lines.append(f"- {key}: {value}")
        else:
            lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("## 4. 模型参数")
    lines.append("")
    n_params = sum(p.numel() for p in trainer.model.parameters())
    lines.append(f"- 总参数量: {n_params:,}")
    lines.append("")

    lines.append("## 5. 训练历史")
    lines.append("")
    lines.append("| Epoch | Loss Total | Loss Cum | Loss Haz | L2 Penalty |")
    lines.append("|-------|------------|----------|----------|------------|")
    
    for i in range(0, len(trainer.history["epoch"]), 10):
        epoch = trainer.history["epoch"][i]
        loss_total = trainer.history["loss_total"][i]
        loss_cum = trainer.history["loss_cum"][i]
        loss_haz = trainer.history["loss_haz"][i]
        l2 = trainer.history["l2_penalty"][i]
        lines.append(f"| {epoch} | {loss_total:.6f} | {loss_cum:.6f} | {loss_haz:.6f} | {l2:.6f} |")

    # 最后一行
    last_idx = len(trainer.history["epoch"]) - 1
    lines.append(f"| {trainer.history['epoch'][last_idx]} | "
                 f"{trainer.history['loss_total'][last_idx]:.6f} | "
                 f"{trainer.history['loss_cum'][last_idx]:.6f} | "
                 f"{trainer.history['loss_haz'][last_idx]:.6f} | "
                 f"{trainer.history['l2_penalty'][last_idx]:.6f} |")

    lines.append("")

    lines.append("## 6. 最终损失")
    lines.append("")
    final_loss = trainer.history["loss_total"][-1]
    lines.append(f"- Final loss_total: {final_loss:.6f}")
    lines.append("")

    lines.append("## 7. 训练产物")
    lines.append("")
    lines.append(f"- model_final.pt: 最终 epoch 模型")
    lines.append(f"- model_best.pt: 与 model_final.pt 相同（early_stopping=false）")
    lines.append(f"- training_history.json: 训练历史")
    lines.append(f"- training_loss_curve.png: loss 曲线")
    lines.append(f"- train_config_frozen.json: 训练配置")
    lines.append("")

    lines.append("## 8. 备注")
    lines.append("")
    lines.append("- 训练仅使用 train-dev 数据")
    lines.append("- cal-dev 未参与训练、early stopping 或模型选择")
    lines.append("- heldout 完全隔离，未访问")
    lines.append("- 类别权重从 train-dev 计算，但当前 loss 实现未启用 class weights")
    lines.append("")

    return "\n".join(lines)


def main():
    """主执行流程"""
    print("=" * 70)
    print("SL-RDAF Phase 3: 训练")
    print("=" * 70)

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 设置随机种子
    print("\n[Step 0] 设置随机种子...")
    set_global_seed(20260528)

    # 2. 加载数据
    train_df, cal_df, heldout_df = load_and_process_data()

    # 3. 计算类别权重
    print("\n[Step 2] 计算 train-dev 类别权重...")
    class_weights_results = compute_class_weights(train_df)

    # 4. 构建 DataLoader
    print("\n[Step 3] 构建 DataLoader...")
    train_dataloader = build_dataloader(train_df, batch_size=32, shuffle=True)
    print(f"  train-dev dataloader: {len(train_dataloader)} batches")

    # 5. 初始化模型
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

    # 6. 检测设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  设备: {device}")

    # 7. 初始化训练器
    print("\n[Step 5] 初始化训练器...")
    trainer = MHEORFTrainer(
        model=model,
        device=device,
        learning_rate=0.001,
        weight_decay=0.0001,
        lambda_haz=1.0,
        max_epochs=200,
        batch_size=32,
        gradient_clip_norm=5.0,
        class_weights=None,  # 当前 loss 不支持 class weights
        output_dir=OUTPUT_DIR,
    )

    # 8. 训练
    print("\n[Step 6] 开始训练...")
    history = trainer.fit(train_dataloader)

    # 9. 保存输出
    print("\n[Step 7] 保存训练产物...")
    trainer.save_outputs()
    trainer.plot_loss_curve()

    # 10. 生成报告
    print("\n[Step 8] 生成训练报告...")
    report_md = generate_training_report(trainer, train_df, class_weights_results)
    
    report_path = OUTPUT_DIR / "training_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    
    print(f"  训练报告已保存: {report_path}")

    # 11. 控制台输出
    print("\n" + "=" * 70)
    print("[SL-RDAF Phase 3 Training Completed]")
    print("=" * 70)
    print(f"\nTrain-dev:")
    print(f"  samples: {train_df[SAMPLE_ID_COL].nunique()}")
    print(f"  rows: {len(train_df)}")
    print(f"  final loss: {history['loss_total'][-1]:.6f}")
    print(f"  model parameters: {n_params:,}")
    print(f"\nOutput files:")
    print(f"  {OUTPUT_DIR / 'model_final.pt'}")
    print(f"  {OUTPUT_DIR / 'model_best.pt'}")
    print(f"  {OUTPUT_DIR / 'training_history.json'}")
    print(f"  {OUTPUT_DIR / 'training_loss_curve.png'}")
    print(f"  {OUTPUT_DIR / 'train_config_frozen.json'}")
    print(f"  {OUTPUT_DIR / 'training_report.md'}")
    print(f"  {OUTPUT_DIR / 'class_weights_train_dev.json'}")
    print("=" * 70)

    return trainer, cal_df, heldout_df


if __name__ == "__main__":
    main()
