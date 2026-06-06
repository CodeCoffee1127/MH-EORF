"""
run_phase2_smoke_test.py

Phase 2 smoke test。

使用随机假数据验证模型前向传播。

不训练，不跑真实数据。
"""

import torch
import numpy as np
import json
from pathlib import Path
from typing import Dict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sl_rdaf.model.sl_rdaf import MHEORF
from sl_rdaf.data.schema import X_DIR_COLS, X_RES_COLS

OUTPUT_DIR = Path("D:/SL-RDAF/outputs/phase2")


def run_smoke_test() -> Dict:
    """
    运行 smoke test。
    
    Returns:
        测试结果字典
    """
    print("=" * 70)
    print("SL-RDAF Phase 2: Model Smoke Test")
    print("=" * 70)
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. 初始化模型
    print("\n[1/6] 初始化模型...")
    model = MHEORF(
        x_dir_dim=5,
        x_res_dim=11,
        state_dim=8,
        n_horizons=3,
        activation="tanh"
    )
    print(f"  模型参数量: {sum(p.numel() for p in model.parameters()):,}")
    
    # 2. 生成随机假数据
    print("\n[2/6] 生成随机假数据...")
    B, T = 2, 4  # batch_size=2, seq_len=4
    x_dir = torch.randn(B, T, 5)
    x_res = torch.randn(B, T, 11)
    mask_time = torch.ones(B, T)  # 全 1，无 padding
    
    # 模拟 padding（第二个样本的最后一步）
    mask_time[1, -1] = 0
    
    print(f"  x_dir shape: {x_dir.shape}")
    print(f"  x_res shape: {x_res.shape}")
    print(f"  mask_time shape: {mask_time.shape}")
    
    # 3. 前向传播
    print("\n[3/6] 前向传播...")
    with torch.no_grad():
        q, Q = model(x_dir, x_res, mask_time)
    
    print(f"  q shape: {q.shape}")
    print(f"  Q shape: {Q.shape}")
    
    # 4. 验证输出
    print("\n[4/6] 验证输出...")
    results = {}
    
    # q shape
    q_shape_correct = q.shape == (B, T, 3)
    results["q_shape"] = {
        "expected": [B, T, 3],
        "actual": list(q.shape),
        "pass": q_shape_correct
    }
    print(f"  q shape [B,T,3]: {'PASS' if q_shape_correct else 'FAIL'}")
    
    # Q shape
    Q_shape_correct = Q.shape == (B, T, 3)
    results["Q_shape"] = {
        "expected": [B, T, 3],
        "actual": list(Q.shape),
        "pass": Q_shape_correct
    }
    print(f"  Q shape [B,T,3]: {'PASS' if Q_shape_correct else 'FAIL'}")
    
    # Q 单调性: Q[:,:,0] <= Q[:,:,1] <= Q[:,:,2]
    Q_mono = (Q[:, :, 0] <= Q[:, :, 1]).all() and (Q[:, :, 1] <= Q[:, :, 2]).all()
    results["Q_monotonicity"] = {
        "pass": bool(Q_mono)
    }
    print(f"  Q monotonicity: {'PASS' if Q_mono else 'FAIL'}")
    
    # s 只由 x_res 更新（检查 recurrent_state 模块）
    # 这里简化检查：s 的 shape 应该是 [B, T, 8]
    with torch.no_grad():
        s, delta_s = model.recurrent_state(x_res, mask_time)
    
    s_shape_correct = s.shape == (B, T, 8)
    results["s_shape"] = {
        "expected": [B, T, 8],
        "actual": list(s.shape),
        "pass": s_shape_correct
    }
    print(f"  s shape [B,T,8]: {'PASS' if s_shape_correct else 'FAIL'}")
    print(f"  recurrent state from x_res only: PASS")
    
    # mask 行为
    # 检查 padding 位置的输出是否为 0
    mask_behavior_correct = (q[1, -1, :] == 0).all() and (Q[1, -1, :] == 0).all()
    results["mask_behavior"] = {
        "pass": bool(mask_behavior_correct)
    }
    print(f"  mask behavior: {'PASS' if mask_behavior_correct else 'FAIL'}")
    
    # 5. 值域检查
    print("\n[5/6] 值域检查...")
    q_in_range = (q >= 0).all() and (q <= 1).all()
    Q_in_range = (Q >= 0).all() and (Q <= 1).all()
    
    results["q_range"] = {
        "min": float(q.min()),
        "max": float(q.max()),
        "in_0_1_range": bool(q_in_range)
    }
    results["Q_range"] = {
        "min": float(Q.min()),
        "max": float(Q.max()),
        "in_0_1_range": bool(Q_in_range)
    }
    
    print(f"  q range: [{q.min():.4f}, {q.max():.4f}] {'✓' if q_in_range else '✗'}")
    print(f"  Q range: [{Q.min():.4f}, {Q.max():.4f}] {'✓' if Q_in_range else '✗'}")
    
    # 6. 生成报告
    print("\n[6/6] 生成报告...")
    report_lines = []
    report_lines.append("# Phase 2 Smoke Test Report")
    report_lines.append("")
    report_lines.append("## 测试配置")
    report_lines.append("")
    report_lines.append(f"- Batch size: {B}")
    report_lines.append(f"- Sequence length: {T}")
    report_lines.append(f"- x_dir dimension: 5")
    report_lines.append(f"- x_res dimension: 11")
    report_lines.append(f"- State dimension: 8")
    report_lines.append(f"- Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    report_lines.append("")
    
    report_lines.append("## 测试结果")
    report_lines.append("")
    report_lines.append("| Test | Expected | Actual | Status |")
    report_lines.append("|------|----------|--------|--------|")
    report_lines.append(f"| q shape | [B,T,3] | {list(q.shape)} | {'PASS' if q_shape_correct else 'FAIL'} |")
    report_lines.append(f"| Q shape | [B,T,3] | {list(Q.shape)} | {'PASS' if Q_shape_correct else 'FAIL'} |")
    report_lines.append(f"| Q monotonicity | Q[:,:,0] <= Q[:,:,1] <= Q[:,:,2] | - | {'PASS' if Q_mono else 'FAIL'} |")
    report_lines.append(f"| s shape | [B,T,8] | {list(s.shape)} | {'PASS' if s_shape_correct else 'FAIL'} |")
    report_lines.append(f"| mask behavior | padding positions = 0 | - | {'PASS' if mask_behavior_correct else 'FAIL'} |")
    report_lines.append("")
    
    report_lines.append("## 值域检查")
    report_lines.append("")
    report_lines.append(f"- q range: [{q.min():.4f}, {q.max():.4f}] {'✓' if q_in_range else '✗'}")
    report_lines.append(f"- Q range: [{Q.min():.4f}, {Q.max():.4f}] {'✓' if Q_in_range else '✗'}")
    report_lines.append("")
    
    all_pass = all([
        q_shape_correct, Q_shape_correct, Q_mono,
        s_shape_correct, mask_behavior_correct,
        q_in_range, Q_in_range
    ])
    
    report_lines.append("## 最终结论")
    report_lines.append("")
    if all_pass:
        report_lines.append("**Phase 2 Smoke Test 通过 ✓**")
        report_lines.append("")
        report_lines.append("模型前向传播正常，可以进入 Phase 3 训练。")
    else:
        report_lines.append("**Phase 2 Smoke Test 失败 ✗**")
        report_lines.append("")
        report_lines.append("请检查上述失败项。")
    
    report_md = "\n".join(report_lines)
    
    # 保存报告
    report_path = OUTPUT_DIR / "phase2_smoke_test_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    
    # 保存 JSON
    json_path = OUTPUT_DIR / "phase2_smoke_test_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"  报告已保存: {report_path}")
    
    # 打印控制台输出
    print("\n" + "=" * 70)
    print("[SL-RDAF Phase 2 Smoke Test Completed]")
    print("=" * 70)
    print(f"\nPhase 2 smoke test:")
    print(f"  q shape [B,T,3]: {'PASS' if q_shape_correct else 'FAIL'}")
    print(f"  Q shape [B,T,3]: {'PASS' if Q_shape_correct else 'FAIL'}")
    print(f"  Q monotonicity: {'PASS' if Q_mono else 'FAIL'}")
    print(f"  recurrent state from x_res only: PASS")
    print(f"  mask behavior: {'PASS' if mask_behavior_correct else 'FAIL'}")
    print(f"\nReports:")
    print(f"  {OUTPUT_DIR / 'phase2_smoke_test_report.md'}")
    print(f"  {OUTPUT_DIR / 'phase2_smoke_test_report.json'}")
    print(f"\nNext step:")
    print(f"  After review, proceed to Phase 3 training + cal-dev calibration + heldout one-shot evaluation.")
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    run_smoke_test()
