"""
loss.py

BCE loss with masking and class weights.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional


class MaskedBCELossTrilinear(nn.Module):
    """
    带掩码的 BCE 损失。
    
    Loss = -\frac{1}{N} \sum_{i,t,h} valid_{i,t,h} · [y_{i,t,h} · log(Q_{i,t,h}) + (1-y_{i,t,h}) · log(1-Q_{i,t,h})]
    """
    
    def __init__(self, class_weights: Optional[torch.Tensor] = None):
        """
        Args:
            class_weights: [3]，每个 horizon 的类别权重
        """
        super().__init__()
        self.register_buffer("class_weights", class_weights)
    
    def forward(
        self,
        Q: torch.Tensor,
        y: torch.Tensor,
        valid_mask: torch.Tensor
    ) -> torch.Tensor:
        """
        前向传播。
        
        Args:
            Q: [B, T, 3]，预测的累积风险
            y: [B, T, 3]，标签
            valid_mask: [B, T, 3]，有效掩码
        
        Returns:
            loss: 标量损失
        """
        # BCE loss
        bce = F.binary_cross_entropy(Q, y, reduction="none")  # [B, T, 3]
        
        # 应用 valid mask
        masked_bce = bce * valid_mask  # [B, T, 3]
        
        # 应用 class weights
        if self.class_weights is not None:
            # class_weights: [3] -> [1, 1, 3]
            weighted_bce = masked_bce * self.class_weights.unsqueeze(0).unsqueeze(0)
        else:
            weighted_bce = masked_bce
        
        # 平均损失
        n_valid = valid_mask.sum()
        if n_valid > 0:
            loss = weighted_bce.sum() / n_valid
        else:
            loss = weighted_bce.sum()  # 返回 0
        
        return loss
