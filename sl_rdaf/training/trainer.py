"""
trainer.py

SL-RDAF 模型训练器。

固定训练配置:
- optimizer: AdamW
- learning_rate: 0.001
- weight_decay: 0.0001
- lambda_haz: 1.0
- max_epochs: 200
- batch_size: 32
- early_stopping: false
- gradient_clip_norm: 5.0
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
import json

from sl_rdaf.model.sl_rdaf import MHEORF
from sl_rdaf.model.loss import MaskedBCELossTrilinear
from sl_rdaf.training.checkpointing import save_checkpoint, save_training_history


class MHEORFTrainer:
    """
    SL-RDAF 训练器。
    """

    def __init__(
        self,
        model: MHEORF,
        device: torch.device,
        learning_rate: float = 0.001,
        weight_decay: float = 0.0001,
        lambda_haz: float = 1.0,
        max_epochs: int = 200,
        batch_size: int = 32,
        gradient_clip_norm: float = 5.0,
        class_weights: Optional[torch.Tensor] = None,
        output_dir: Path = Path("D:/SL-RDAF/outputs/training"),
    ):
        """
        Args:
            model: SL-RDAF 模型
            device: 计算设备
            learning_rate: 学习率
            weight_decay: 权重衰减
            lambda_haz: hazard loss 权重
            max_epochs: 最大 epoch 数
            batch_size: batch size
            gradient_clip_norm: 梯度裁剪范数
            class_weights: 类别权重 [3]
            output_dir: 输出目录
        """
        self.model = model.to(device)
        self.device = device
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.lambda_haz = lambda_haz
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self.gradient_clip_norm = gradient_clip_norm
        self.class_weights = class_weights
        self.output_dir = output_dir

        # 优化器
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay,
        )

        # Loss: 累积风险 loss + hazard loss
        self.cum_loss_fn = MaskedBCELossTrilinear(class_weights=class_weights)
        
        # 如果 class_weights 为 None，创建等权重
        if class_weights is None:
            class_weights_haz = torch.ones(3)
        else:
            class_weights_haz = class_weights
        
        self.haz_loss_fn = MaskedBCELossTrilinear(class_weights=class_weights_haz)

        # 训练历史
        self.history = {
            "epoch": [],
            "loss_total": [],
            "loss_cum": [],
            "loss_haz": [],
            "l2_penalty": [],
        }

    def _prepare_batch(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        y_cum: torch.Tensor,
        y_haz: torch.Tensor,
        valid_mask_cum: torch.Tensor,
        valid_mask_haz: torch.Tensor,
    ) -> Tuple:
        """
        准备 batch 数据，移动到 device。

        Returns:
            移动到 device 后的 tuple
        """
        return (
            x_dir.to(self.device),
            x_res.to(self.device),
            y_cum.to(self.device),
            y_haz.to(self.device),
            valid_mask_cum.to(self.device),
            valid_mask_haz.to(self.device),
        )

    def train_epoch(
        self,
        dataloader: DataLoader,
    ) -> Dict[str, float]:
        """
        训练一个 epoch。

        Args:
            dataloader: train-dev dataloader

        Returns:
            epoch 级别的 loss 统计
        """
        self.model.train()
        
        total_loss = 0.0
        total_cum_loss = 0.0
        total_haz_loss = 0.0
        total_l2 = 0.0
        n_batches = 0

        for batch in dataloader:
            x_dir, x_res, y_cum, y_haz, valid_mask_cum, valid_mask_haz = self._prepare_batch(*batch)

            # 前向传播
            self.optimizer.zero_grad()
            
            q, Q = self.model(x_dir, x_res, mask_time=None)
            
            # q: [B, T, 3], Q: [B, T, 3]
            
            # 累积风险 loss
            loss_cum = self.cum_loss_fn(Q, y_cum, valid_mask_cum)
            
            # Hazard loss
            loss_haz = self.haz_loss_fn(q, y_haz, valid_mask_haz)
            
            # 总 loss
            loss_total = loss_cum + self.lambda_haz * loss_haz
            
            # L2 penalty (from weight_decay)
            l2_penalty = sum(p.pow(2.0).sum() for p in self.model.parameters())
            
            # 反向传播
            loss_total.backward()
            
            # 梯度裁剪
            torch.nn.utils.clip_grad_norm_(
                self.model.parameters(),
                max_norm=self.gradient_clip_norm,
            )
            
            self.optimizer.step()

            # 统计
            total_loss += loss_total.item()
            total_cum_loss += loss_cum.item()
            total_haz_loss += loss_haz.item()
            total_l2 += l2_penalty.item()
            n_batches += 1

        # 平均
        avg_loss = total_loss / n_batches if n_batches > 0 else 0.0
        avg_cum_loss = total_cum_loss / n_batches if n_batches > 0 else 0.0
        avg_haz_loss = total_haz_loss / n_batches if n_batches > 0 else 0.0
        avg_l2 = total_l2 / n_batches if n_batches > 0 else 0.0

        return {
            "loss_total": avg_loss,
            "loss_cum": avg_cum_loss,
            "loss_haz": avg_haz_loss,
            "l2_penalty": avg_l2,
        }

    def fit(
        self,
        train_dataloader: DataLoader,
    ) -> Dict:
        """
        训练模型。

        Args:
            train_dataloader: train-dev dataloader

        Returns:
            训练历史字典
        """
        print(f"\n  开始训练...")
        print(f"  设备: {self.device}")
        print(f"  Max epochs: {self.max_epochs}")
        print(f"  Batch size: {self.batch_size}")
        print(f"  Learning rate: {self.learning_rate}")
        print(f"  Weight decay: {self.weight_decay}")
        print(f"  Lambda haz: {self.lambda_haz}")
        print(f"  Gradient clip norm: {self.gradient_clip_norm}")
        print(f"  Early stopping: false")
        print()

        for epoch in range(1, self.max_epochs + 1):
            epoch_stats = self.train_epoch(train_dataloader)

            # 记录历史
            self.history["epoch"].append(epoch)
            self.history["loss_total"].append(epoch_stats["loss_total"])
            self.history["loss_cum"].append(epoch_stats["loss_cum"])
            self.history["loss_haz"].append(epoch_stats["loss_haz"])
            self.history["l2_penalty"].append(epoch_stats["l2_penalty"])

            # 每 10 epoch 打印
            if epoch % 10 == 0 or epoch == 1:
                print(f"  Epoch [{epoch:3d}/{self.max_epochs}] "
                      f"loss_total={epoch_stats['loss_total']:.6f} "
                      f"loss_cum={epoch_stats['loss_cum']:.6f} "
                      f"loss_haz={epoch_stats['loss_haz']:.6f} "
                      f"l2={epoch_stats['l2_penalty']:.6f}")

        print(f"\n  训练完成")
        print(f"  Final loss: {epoch_stats['loss_total']:.6f}")

        return self.history

    def save_outputs(self):
        """
        保存训练产物。
        """
        print(f"\n  保存训练产物...")

        # 保存最终模型
        save_checkpoint(
            self.model,
            self.optimizer,
            epoch=self.max_epochs,
            loss=self.history["loss_total"][-1],
            output_dir=self.output_dir,
            filename="model_final.pt",
            additional_state={
                "learning_rate": self.learning_rate,
                "weight_decay": self.weight_decay,
                "lambda_haz": self.lambda_haz,
                "batch_size": self.batch_size,
                "max_epochs": self.max_epochs,
                "seed": 20260528,
            },
        )

        # model_best.pt = model_final.pt (因为 early_stopping=false)
        save_checkpoint(
            self.model,
            self.optimizer,
            epoch=self.max_epochs,
            loss=self.history["loss_total"][-1],
            output_dir=self.output_dir,
            filename="model_best.pt",
            additional_state={
                "note": "model_best.pt is identical to model_final.pt because early_stopping=false and no cal-dev model selection is used.",
            },
        )

        # 保存训练历史
        save_training_history(self.history, self.output_dir)

        # 保存训练配置
        config = {
            "seed": 20260528,
            "optimizer": "AdamW",
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "lambda_haz": self.lambda_haz,
            "max_epochs": self.max_epochs,
            "batch_size": self.batch_size,
            "early_stopping": False,
            "gradient_clip_norm": self.gradient_clip_norm,
            "device": str(self.device),
            "model_config": {
                "dim_x_dir": 5,
                "dim_x_res": 11,
                "dim_s": 8,
                "horizons": [1, 2, 3],
                "lead_steps": [1, 2, 3],
                "use_direction_constraints": True,
                "recurrent_state_from": "x_res_only",
            },
        }

        config_path = self.output_dir / "train_config_frozen.yaml"
        # 用 JSON 格式保存（比 YAML 更简单）
        with open(self.output_dir / "train_config_frozen.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"  训练配置已保存: {self.output_dir / 'train_config_frozen.json'}")

    def plot_loss_curve(self):
        """
        绘制训练 loss 曲线。
        """
        try:
            import matplotlib
            matplotlib.use('Agg')  # 非交互式后端
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, 6))

            epochs = self.history["epoch"]
            ax.plot(epochs, self.history["loss_total"], label="loss_total", linewidth=2)
            ax.plot(epochs, self.history["loss_cum"], label="loss_cum", linewidth=1.5, alpha=0.7)
            ax.plot(epochs, self.history["loss_haz"], label="loss_haz", linewidth=1.5, alpha=0.7)

            ax.set_xlabel("Epoch", fontsize=12)
            ax.set_ylabel("Loss", fontsize=12)
            ax.set_title("SL-RDAF Training Loss Curve", fontsize=14)
            ax.legend(fontsize=11)
            ax.grid(True, alpha=0.3)

            loss_curve_path = self.output_dir / "training_loss_curve.png"
            plt.savefig(loss_curve_path, dpi=150, bbox_inches="tight")
            plt.close()

            print(f"  Loss 曲线已保存: {loss_curve_path}")

        except ImportError:
            print(f"  警告: matplotlib 未安装，跳过 loss 曲线绘制")
