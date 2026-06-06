"""
checkpointing.py

模型检查点保存和加载。
"""

import torch
from pathlib import Path
from typing import Optional, Dict
import json


def save_checkpoint(
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    loss: float,
    output_dir: Path,
    filename: str = "model_final.pt",
    additional_state: Optional[Dict] = None,
):
    """
    保存模型检查点。

    Args:
        model: PyTorch 模型
        optimizer: 优化器
        epoch: 当前 epoch
        loss: 当前 loss
        output_dir: 输出目录
        filename: 文件名
        additional_state: 额外状态字典
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "loss": loss,
    }

    if additional_state is not None:
        checkpoint.update(additional_state)

    checkpoint_path = output_dir / filename
    torch.save(checkpoint, checkpoint_path)
    
    print(f"  检查点已保存: {checkpoint_path} (epoch={epoch}, loss={loss:.6f})")
    
    return checkpoint_path


def load_checkpoint(
    model: torch.nn.Module,
    checkpoint_path: Path,
    optimizer: Optional[torch.optim.Optimizer] = None,
) -> Dict:
    """
    加载模型检查点。

    Args:
        model: PyTorch 模型
        checkpoint_path: 检查点路径
        optimizer: 优化器（可选）

    Returns:
        检查点字典
    """
    checkpoint = torch.load(checkpoint_path, map_location="cpu")

    model.load_state_dict(checkpoint["model_state_dict"])

    if optimizer is not None and "optimizer_state_dict" in checkpoint:
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

    print(f"  检查点已加载: {checkpoint_path} (epoch={checkpoint['epoch']}, loss={checkpoint['loss']:.6f})")

    return checkpoint


def save_training_history(
    history: Dict,
    output_dir: Path,
    filename: str = "training_history.json",
):
    """
    保存训练历史。

    Args:
        history: 训练历史字典
        output_dir: 输出目录
        filename: 文件名
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    history_path = output_dir / filename
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    
    print(f"  训练历史已保存: {history_path}")
