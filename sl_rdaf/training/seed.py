"""
seed.py

设置全局随机种子，确保训练可复现。
"""

import random
import numpy as np
import torch


def set_global_seed(seed: int = 20260528):
    """
    设置全局随机种子。

    固定:
    - random
    - numpy
    - torch
    - torch.cuda (如果可用)
    - torch.backends.cudnn

    Args:
        seed: 随机种子
    """
    # Python random
    random.seed(seed)
    
    # NumPy
    np.random.seed(seed)
    
    # PyTorch
    torch.manual_seed(seed)
    
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    
    # CuDNN
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    
    print(f"  全局随机种子已设置: {seed}")
    print(f"  torch.backends.cudnn.deterministic = True")
    print(f"  torch.backends.cudnn.benchmark = False")
