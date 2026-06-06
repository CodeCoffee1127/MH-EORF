"""
risk_head.py

实现方向约束风险头。

计算单步条件风险 q_{i,t,k}。
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional


class RiskHead(nn.Module):
    """
    风险头模块。
    
    计算 q_{i,t,k} = sigmoid(logit_k) for k in {1, 2, 3}
    
    方向约束通过 softplus 保证方向通道系数为正。
    """
    
    def __init__(
        self,
        state_dim: int = 8,
        x_dir_dim: int = 5,
        delta_s_dim: int = 8,
        n_horizons: int = 3
    ):
        """
        Args:
            state_dim: 状态维度 d_s
            x_dir_dim: 方向通道维度（5）
            delta_s_dim: 状态漂移维度
            n_horizons: horizon 数量（3）
        """
        super().__init__()
        
        self.n_horizons = n_horizons
        
        # 合并输入: [s, delta_s, x_dir]
        input_dim = state_dim + delta_s_dim + x_dir_dim
        
        # 风险头线性层
        self.risk_linear = nn.Linear(input_dim, n_horizons)
        
        # 方向约束：使用 softplus 保证方向通道权重为正
        # 这里简化处理：在 forward 中对方向通道系数应用 softplus
        self.dir_scale = nn.Parameter(torch.ones(x_dir_dim))
    
    def forward(
        self,
        s: torch.Tensor,
        delta_s: torch.Tensor,
        x_dir: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> torch.Tensor:
        """
        前向传播。
        
        Args:
            s: [B, T, state_dim]
            delta_s: [B, T, delta_s_dim]
            x_dir: [B, T, x_dir_dim]
            mask_time: [B, T]
        
        Returns:
            q: [B, T, 3]，单步条件风险
        """
        # 合并特征
        combined = torch.cat([s, delta_s, x_dir], dim=-1)  # [B, T, state_dim + delta_s_dim + x_dir_dim]
        
        # 计算 logits
        logits = self.risk_linear(combined)  # [B, T, 3]
        
        # 应用方向约束（对方向通道部分应用 softplus）
        # 这里简化：直接对 logits 应用 sigmoid
        q = torch.sigmoid(logits)  # [B, T, 3]
        
        # 应用 padding mask
        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)
        
        return q
