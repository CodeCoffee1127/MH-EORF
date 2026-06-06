"""
sl_rdaf.py

SL-RDAF 主模型。

整合递推状态、方向约束风险头和多视野累积风险。
"""

import torch
import torch.nn as nn
from typing import Tuple, Optional
from sl_rdaf.model.recurrent_state import RecurrentState
from sl_rdaf.model.risk_head import RiskHead


class MHEORF(nn.Module):
    """
    SL-RDAF 模型。
    
    前向传播:
    1. x_res -> s_{i,t}, \Delta s_{i,t}
    2. s, \Delta s, x_dir -> q_{i,t,k}
    3. q -> Q_{i,t,h}（累积风险）
    """
    
    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        """
        Args:
            x_dir_dim: 方向通道维度（5）
            x_res_dim: 残差通道维度（11）
            state_dim: 状态维度 d_s（8）
            n_horizons: horizon 数量（3）
            activation: 激活函数
        """
        super().__init__()
        
        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons
        
        # 递推状态模块
        self.recurrent_state = RecurrentState(
            x_res_dim=x_res_dim,
            state_dim=state_dim,
            activation=activation
        )
        
        # 风险头模块
        self.risk_head = RiskHead(
            state_dim=state_dim,
            x_dir_dim=x_dir_dim,
            delta_s_dim=state_dim,
            n_horizons=n_horizons
        )
    
    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        前向传播。
        
        Args:
            x_dir: [B, T, 5]，方向通道
            x_res: [B, T, 11]，残差通道
            mask_time: [B, T]，padding mask
        
        Returns:
            (q, Q):
                - q: [B, T, 3]，单步条件风险
                - Q: [B, T, 3]，多视野累积风险
        """
        # 1. 计算递推状态
        s, delta_s = self.recurrent_state(x_res, mask_time)
        
        # 2. 计算单步条件风险
        q = self.risk_head(s, delta_s, x_dir, mask_time)
        
        # 3. 计算累积风险 Q_{i,t,h}
        # Q_{i,t,h} = 1 - \prod_{k=1}^{h} (1 - q_{i,t,k})
        # 或者使用 hazard 累积: Q_{i,t,h} = 1 - \prod_{k=1}^{h} (1 - q_{i,t,k})
        Q = self._compute_cumulative_risk(q)
        
        return q, Q
    
    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        """
        计算累积风险。
        
        Q_{i,t,h} = 1 - \prod_{k=1}^{h} (1 - q_{i,t,k})
        
        保证单调性: Q_{i,t,1} <= Q_{i,t,2} <= Q_{i,t,3}
        
        Args:
            q: [B, T, 3]
        
        Returns:
            Q: [B, T, 3]
        """
        # 生存概率: S_{i,t,k} = 1 - q_{i,t,k}
        survival = 1.0 - q  # [B, T, 3]
        
        # 累积生存概率: \prod_{k=1}^{h} S_{i,t,k}
        cum_survival = torch.cumprod(survival, dim=-1)  # [B, T, 3]
        
        # 累积风险: Q_{i,t,h} = 1 - cum_survival_{h}
        Q = 1.0 - cum_survival  # [B, T, 3]
        
        return Q
