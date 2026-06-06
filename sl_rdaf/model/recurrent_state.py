"""
recurrent_state.py

实现递推状态 s_{i,t} 的计算。

s_{i,t} 只由 x^{res}_{i,t} 更新。
"""

import torch
import torch.nn as nn
from typing import Tuple


class RecurrentState(nn.Module):
    """
    递推状态模块。
    
    s_{i,t} = f(W_s · x^{res}_{i,t} + b_s)
    
    其中 f 是激活函数（默认 tanh）。
    """
    
    def __init__(
        self,
        x_res_dim: int = 11,
        state_dim: int = 8,
        activation: str = "tanh"
    ):
        """
        Args:
            x_res_dim: x_res 的维度（默认 11）
            state_dim: 状态维度 d_s（默认 8）
            activation: 激活函数（tanh 或 relu）
        """
        super().__init__()
        
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        
        # 投影层: x_res -> state
        self.W_s = nn.Linear(x_res_dim, state_dim)
        
        # 激活函数
        if activation == "tanh":
            self.activation = nn.Tanh()
        elif activation == "relu":
            self.activation = nn.ReLU()
        else:
            raise ValueError(f"不支持的激活函数: {activation}")
    
    def forward(
        self,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        前向传播。
        
        Args:
            x_res: [B, T, x_res_dim]
            mask_time: [B, T]，1 表示有效，0 表示 padding
        
        Returns:
            (s, delta_s): 
                - s: [B, T, state_dim]，递推状态
                - delta_s: [B, T, state_dim]，状态漂移 = s_{i,t} - s_{i,t-1}
        """
        B, T, _ = x_res.shape
        
        # 初始化状态
        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        
        # 递推计算
        for t in range(T):
            if t == 0:
                # 第一步：s_{i,0} = activation(W_s · x_res_{i,0})
                s[:, t, :] = self.activation(self.W_s(x_res[:, t, :]))
            else:
                # 递推：s_{i,t} = activation(W_s · x_res_{i,t} + s_{i,t-1})
                # 注意：这里简化为只由 x_res 更新，不显式依赖 s_{i,t-1}
                # 实际论文公式可能是 s_{i,t} = f(W_s · x_res_{i,t})
                s[:, t, :] = self.activation(self.W_s(x_res[:, t, :]))
            
            # 应用 padding mask
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)
        
        # 计算状态漂移
        delta_s = torch.zeros_like(s)
        delta_s[:, 1:, :] = s[:, 1:, :] - s[:, :-1, :]
        # delta_s[:, 0, :] = 0（第一步没有漂移）
        
        return s, delta_s
