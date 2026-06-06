"""
ablation_models.py

§4.4 消融实验模型定义。

11 项消融：
- A-Dir: 去掉方向约束（softplus → 自由参数）
- A-Ch: 破坏通道分离（x_dir 混入 recurrent state）
- A-B: 去掉 I_minus_i_t（置零）
- A-Bp: 去掉 I_plus_i_t（置零）
- A-Rho: 去掉 rho_i_t（置零）
- A-Var: 去掉 U_i_t（置零）
- A-Net: 依赖极性合并为净量
- A-Rec: 去掉递推可靠性状态 s_i_t
- A-Drift: 去掉状态漂移 Delta s_i_t
- A-Haz: 去掉 hazard accumulation（direct horizon probability）
"""

import torch
import torch.nn as nn
from typing import Tuple, Optional


# ============================================================
# A-Dir: 去掉方向约束
# ============================================================

class AblationDirModel(nn.Module):
    """
    A-Dir: 去掉方向约束。

    修改：
    - risk head 中对方向变量的 softplus 非负约束改为自由参数
    - 其他结构保持与完整模型一致
    - 仍使用 recurrent state
    - 仍使用 hazard accumulation
    """

    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        # 递推状态模块（与主模型相同）
        self.recurrent_state = nn.Sequential(
            nn.Linear(x_res_dim, state_dim),
            nn.Tanh() if activation == "tanh" else nn.ReLU()
        )

        # 风险头（去掉方向约束）
        input_dim = state_dim + state_dim + x_dir_dim
        self.risk_linear = nn.Linear(input_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x_dir: [B, 5] 或 [B, T, 5]
            x_res: [B, 11] 或 [B, T, 11]
            mask_time: [B, T] 或 None

        Returns:
            (q, Q): q=[B, 3], Q=[B, 3] 或 q=[B, T, 3], Q=[B, T, 3]
        """
        # 处理 2D 输入
        if x_res.dim() == 2:
            x_res = x_res.unsqueeze(1)  # [B, 1, 11]
            x_dir = x_dir.unsqueeze(1)  # [B, 1, 5]
            squeeze_time = True
        else:
            squeeze_time = False
        
        B, T, _ = x_res.shape

        # 1. 计算递推状态
        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        for t in range(T):
            s[:, t, :] = self.recurrent_state(x_res[:, t, :])
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)

        # 2. 计算状态漂移
        delta_s = torch.zeros_like(s)
        delta_s[:, 1:, :] = s[:, 1:, :] - s[:, :-1, :]

        # 3. 风险头（无方向约束）
        combined = torch.cat([s, delta_s, x_dir], dim=-1)
        logits = self.risk_linear(combined)
        q = torch.sigmoid(logits)

        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)

        # 4. 累积风险
        Q = self._compute_cumulative_risk(q)

        return q, Q

    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        survival = 1.0 - q
        cum_survival = torch.cumprod(survival, dim=-1)
        Q = 1.0 - cum_survival
        return Q


# ============================================================
# A-Ch: 破坏通道分离
# ============================================================

class AblationChModel(nn.Module):
    """
    A-Ch: 破坏通道分离。

    修改：
    - 将 x_dir 混入 recurrent state 输入
    - s_i_t 不再只由 x_res 生成
    - 原始 direction head 仍保留
    """

    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        # 递推状态模块（使用 concat(x_res, x_dir)）
        self.recurrent_state = nn.Sequential(
            nn.Linear(x_res_dim + x_dir_dim, state_dim),
            nn.Tanh() if activation == "tanh" else nn.ReLU()
        )

        # 风险头
        input_dim = state_dim + state_dim + x_dir_dim
        self.risk_linear = nn.Linear(input_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, _ = x_res.shape

        # 1. 计算递推状态（使用 x_res 和 x_dir）
        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        for t in range(T):
            combined_res_dir = torch.cat([x_res[:, t, :], x_dir[:, t, :]], dim=-1)
            s[:, t, :] = self.recurrent_state(combined_res_dir)
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)

        # 2. 状态漂移
        delta_s = torch.zeros_like(s)
        delta_s[:, 1:, :] = s[:, 1:, :] - s[:, :-1, :]

        # 3. 风险头
        combined = torch.cat([s, delta_s, x_dir], dim=-1)
        logits = self.risk_linear(combined)
        q = torch.sigmoid(logits)

        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)

        # 4. 累积风险
        Q = self._compute_cumulative_risk(q)

        return q, Q

    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        survival = 1.0 - q
        cum_survival = torch.cumprod(survival, dim=-1)
        Q = 1.0 - cum_survival
        return Q


# ============================================================
# A-B: 去掉 I_minus_i_t
# ============================================================

class AblationBModel(nn.Module):
    """
    A-B: 去掉误导性依赖 I_minus_i_t。

    修改：
    - 将 x_dir 中 I_minus_i_t 置零
    - 其他结构保持完整模型一致
    """

    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        self.recurrent_state = nn.Sequential(
            nn.Linear(x_res_dim, state_dim),
            nn.Tanh() if activation == "tanh" else nn.ReLU()
        )

        input_dim = state_dim + state_dim + x_dir_dim
        self.risk_linear = nn.Linear(input_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, _ = x_res.shape

        # 将 I_minus_i_t（索引 3）置零
        x_dir_modified = x_dir.clone()
        x_dir_modified[:, :, 3] = 0.0

        # 1. 递推状态
        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        for t in range(T):
            s[:, t, :] = self.recurrent_state(x_res[:, t, :])
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)

        # 2. 状态漂移
        delta_s = torch.zeros_like(s)
        delta_s[:, 1:, :] = s[:, 1:, :] - s[:, :-1, :]

        # 3. 风险头
        combined = torch.cat([s, delta_s, x_dir_modified], dim=-1)
        logits = self.risk_linear(combined)
        q = torch.sigmoid(logits)

        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)

        # 4. 累积风险
        Q = self._compute_cumulative_risk(q)

        return q, Q

    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        survival = 1.0 - q
        cum_survival = torch.cumprod(survival, dim=-1)
        Q = 1.0 - cum_survival
        return Q


# ============================================================
# A-Bp: 去掉 I_plus_i_t
# ============================================================

class AblationBpModel(nn.Module):
    """
    A-Bp: 去掉支持性依赖 I_plus_i_t。

    修改：
    - 将 x_dir 中 I_plus_i_t 置零
    """

    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        self.recurrent_state = nn.Sequential(
            nn.Linear(x_res_dim, state_dim),
            nn.Tanh() if activation == "tanh" else nn.ReLU()
        )

        input_dim = state_dim + state_dim + x_dir_dim
        self.risk_linear = nn.Linear(input_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, _ = x_res.shape

        # 将 I_plus_i_t（索引 4）置零
        x_dir_modified = x_dir.clone()
        x_dir_modified[:, :, 4] = 0.0

        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        for t in range(T):
            s[:, t, :] = self.recurrent_state(x_res[:, t, :])
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)

        delta_s = torch.zeros_like(s)
        delta_s[:, 1:, :] = s[:, 1:, :] - s[:, :-1, :]

        combined = torch.cat([s, delta_s, x_dir_modified], dim=-1)
        logits = self.risk_linear(combined)
        q = torch.sigmoid(logits)

        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)

        Q = self._compute_cumulative_risk(q)

        return q, Q

    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        survival = 1.0 - q
        cum_survival = torch.cumprod(survival, dim=-1)
        Q = 1.0 - cum_survival
        return Q


# ============================================================
# A-Rho: 去掉 rho_i_t
# ============================================================

class AblationRhoModel(nn.Module):
    """
    A-Rho: 去掉历史风险残留 rho_i_t。

    修改：
    - 将 x_dir 中 rho_i_t 置零
    """

    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        self.recurrent_state = nn.Sequential(
            nn.Linear(x_res_dim, state_dim),
            nn.Tanh() if activation == "tanh" else nn.ReLU()
        )

        input_dim = state_dim + state_dim + x_dir_dim
        self.risk_linear = nn.Linear(input_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, _ = x_res.shape

        # 将 rho_i_t（索引 2）置零
        x_dir_modified = x_dir.clone()
        x_dir_modified[:, :, 2] = 0.0

        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        for t in range(T):
            s[:, t, :] = self.recurrent_state(x_res[:, t, :])
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)

        delta_s = torch.zeros_like(s)
        delta_s[:, 1:, :] = s[:, 1:, :] - s[:, :-1, :]

        combined = torch.cat([s, delta_s, x_dir_modified], dim=-1)
        logits = self.risk_linear(combined)
        q = torch.sigmoid(logits)

        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)

        Q = self._compute_cumulative_risk(q)

        return q, Q

    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        survival = 1.0 - q
        cum_survival = torch.cumprod(survival, dim=-1)
        Q = 1.0 - cum_survival
        return Q


# ============================================================
# A-Var: 去掉 U_i_t
# ============================================================

class AblationVarModel(nn.Module):
    """
    A-Var: 去掉验证离散度 U_i_t。

    修改：
    - 将 x_res 中 U_i_t 置零
    """

    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        self.recurrent_state = nn.Sequential(
            nn.Linear(x_res_dim, state_dim),
            nn.Tanh() if activation == "tanh" else nn.ReLU()
        )

        input_dim = state_dim + state_dim + x_dir_dim
        self.risk_linear = nn.Linear(input_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, _ = x_res.shape

        # 将 U_i_t（索引 0）置零
        x_res_modified = x_res.clone()
        x_res_modified[:, :, 0] = 0.0

        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        for t in range(T):
            s[:, t, :] = self.recurrent_state(x_res_modified[:, t, :])
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)

        delta_s = torch.zeros_like(s)
        delta_s[:, 1:, :] = s[:, 1:, :] - s[:, :-1, :]

        combined = torch.cat([s, delta_s, x_dir], dim=-1)
        logits = self.risk_linear(combined)
        q = torch.sigmoid(logits)

        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)

        Q = self._compute_cumulative_risk(q)

        return q, Q

    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        survival = 1.0 - q
        cum_survival = torch.cumprod(survival, dim=-1)
        Q = 1.0 - cum_survival
        return Q


# ============================================================
# A-Net: 依赖极性合并为净量
# ============================================================

class AblationNetModel(nn.Module):
    """
    A-Net: 依赖极性合并为净量。

    修改：
    - 用 net_dep_i_t = I_plus_i_t - I_minus_i_t 替代 I_plus_i_t 和 I_minus_i_t
    - x_dir 从 5 维变为 4 维：[1-A_i_t, H_i_t, rho_i_t, net_dep_i_t]
    """

    def __init__(
        self,
        x_dir_dim: int = 4,  # 降维到 4
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        self.recurrent_state = nn.Sequential(
            nn.Linear(x_res_dim, state_dim),
            nn.Tanh() if activation == "tanh" else nn.ReLU()
        )

        input_dim = state_dim + state_dim + x_dir_dim
        self.risk_linear = nn.Linear(input_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, _ = x_res.shape

        # 构造 net_dep = I_plus - I_minus
        # x_dir original: [1-A, H, rho, I_minus, I_plus]
        I_minus = x_dir[:, :, 3:4]  # [B, T, 1]
        I_plus = x_dir[:, :, 4:5]   # [B, T, 1]
        net_dep = I_plus - I_minus

        # 新 x_dir: [1-A, H, rho, net_dep]
        x_dir_modified = torch.cat([
            x_dir[:, :, 0:1],  # 1-A
            x_dir[:, :, 1:2],  # H
            x_dir[:, :, 2:3],  # rho
            net_dep,            # net_dep
        ], dim=-1)

        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        for t in range(T):
            s[:, t, :] = self.recurrent_state(x_res[:, t, :])
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)

        delta_s = torch.zeros_like(s)
        delta_s[:, 1:, :] = s[:, 1:, :] - s[:, :-1, :]

        combined = torch.cat([s, delta_s, x_dir_modified], dim=-1)
        logits = self.risk_linear(combined)
        q = torch.sigmoid(logits)

        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)

        Q = self._compute_cumulative_risk(q)

        return q, Q

    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        survival = 1.0 - q
        cum_survival = torch.cumprod(survival, dim=-1)
        Q = 1.0 - cum_survival
        return Q


# ============================================================
# A-Rec: 去掉递推可靠性状态 s_i_t
# ============================================================

class AblationRecModel(nn.Module):
    """
    A-Rec: 去掉递推可靠性状态 s_i_t。

    修改：
    - 移除 recurrent state s_i_t
    - 风险头不得使用 s_i_t
    - 风险头不得使用 Delta s_i_t
    - 直接使用 x_dir 预测 q_i_t_k
    - 保留 hazard accumulation
    """

    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        # 风险头只使用 x_dir
        self.risk_linear = nn.Linear(x_dir_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        # 直接使用 x_dir 预测风险（无 recurrent state）
        logits = self.risk_linear(x_dir)
        q = torch.sigmoid(logits)

        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)

        Q = self._compute_cumulative_risk(q)

        return q, Q

    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        survival = 1.0 - q
        cum_survival = torch.cumprod(survival, dim=-1)
        Q = 1.0 - cum_survival
        return Q


# ============================================================
# A-Drift: 去掉状态漂移 Delta s_i_t
# ============================================================

class AblationDriftModel(nn.Module):
    """
    A-Drift: 去掉状态漂移 Delta s_i_t。

    修改：
    - 保留 s_i_t
    - 从 risk head 输入中移除 Delta s_i_t
    """

    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        self.recurrent_state = nn.Sequential(
            nn.Linear(x_res_dim, state_dim),
            nn.Tanh() if activation == "tanh" else nn.ReLU()
        )

        # 风险头使用 [s, x_dir]（无 delta_s）
        input_dim = state_dim + x_dir_dim
        self.risk_linear = nn.Linear(input_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, _ = x_res.shape

        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        for t in range(T):
            s[:, t, :] = self.recurrent_state(x_res[:, t, :])
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)

        # 风险头使用 [s, x_dir]（无 delta_s）
        combined = torch.cat([s, x_dir], dim=-1)
        logits = self.risk_linear(combined)
        q = torch.sigmoid(logits)

        if mask_time is not None:
            q = q * mask_time.unsqueeze(-1)

        Q = self._compute_cumulative_risk(q)

        return q, Q

    def _compute_cumulative_risk(self, q: torch.Tensor) -> torch.Tensor:
        survival = 1.0 - q
        cum_survival = torch.cumprod(survival, dim=-1)
        Q = 1.0 - cum_survival
        return Q


# ============================================================
# A-Haz: 去掉 hazard accumulation
# ============================================================

class AblationHazModel(nn.Module):
    """
    A-Haz: 去掉 hazard accumulation。

    修改：
    - 不再输出 q_i_t_k
    - 不再计算 Q_i_t_h = 1 - product(1 - q_i_t_k)
    - 改为直接输出三个独立 horizon sigmoid
    - 仍使用 x_dir, s_i_t, Delta s_i_t
    """

    def __init__(
        self,
        x_dir_dim: int = 5,
        x_res_dim: int = 11,
        state_dim: int = 8,
        n_horizons: int = 3,
        activation: str = "tanh"
    ):
        super().__init__()

        self.x_dir_dim = x_dir_dim
        self.x_res_dim = x_res_dim
        self.state_dim = state_dim
        self.n_horizons = n_horizons

        self.recurrent_state = nn.Sequential(
            nn.Linear(x_res_dim, state_dim),
            nn.Tanh() if activation == "tanh" else nn.ReLU()
        )

        # 风险头使用 [s, delta_s, x_dir]
        input_dim = state_dim + state_dim + x_dir_dim
        self.risk_linear = nn.Linear(input_dim, n_horizons)

    def forward(
        self,
        x_dir: torch.Tensor,
        x_res: torch.Tensor,
        mask_time: torch.Tensor = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T, _ = x_res.shape

        # 1. 递推状态
        s = torch.zeros(B, T, self.state_dim, device=x_res.device)
        for t in range(T):
            s[:, t, :] = self.recurrent_state(x_res[:, t, :])
            if mask_time is not None:
                s[:, t, :] = s[:, t, :] * mask_time[:, t].unsqueeze(-1)

        # 2. 状态漂移
        delta_s = torch.zeros_like(s)
        delta_s[:, 1:, :] = s[:, 1:, :] - s[:, :-1, :]

        # 3. 风险头
        combined = torch.cat([s, delta_s, x_dir], dim=-1)
        logits = self.risk_linear(combined)
        
        # 直接输出三个独立 horizon probability（不再累积）
        Q = torch.sigmoid(logits)  # [B, T, 3]，直接是 Q_hat_h

        if mask_time is not None:
            Q = Q * mask_time.unsqueeze(-1)

        # q 返回与 Q 相同（因为不再有单独的 q）
        q = Q.clone()

        return q, Q
