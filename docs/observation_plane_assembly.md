# Observation Plane Assembly

> **创建时间**: 2026-06-03  
> **步骤**: 第 8 步 — 完整观测平面组装与 CLI 实现  
> **状态**: ✅ 完成

---

## 1. 本步骤目标

实现完整的 §3.2 observation plane assembly：
```
O_i = {(p_{i,t}, v_{i,t}, E_minus_{i,t}, R_{i,t})}_{t=1}^{T_i}
```

将 checkpoint sequence、verification results、dependency sets、perturbation responses 组装为完整的观测平面。

---

## 2. 输入来源

### Preview Mode
从 `artifacts/observation_debug/` 读取：
- `checkpoint_sequence_preview.jsonl`
- `verification_preview.jsonl`
- `dependency_sets_preview.jsonl`
- `perturbation_response_preview.jsonl`

### Dataset Mode
从 `--input` 指向的数据集重新构建：
- 调用 `build_observation_plane(sample, context, protocol)`
- 支持 `--limit` 限制样本数
- 不调用 LLM，不使用 gold SQL，不读取 forbidden fields

---

## 3. 输出文件说明

| 文件 | 说明 |
|------|------|
| `observation_planes.jsonl` | 完整观测平面 JSONL |
| `checkpoints.jsonl` | 扁平化 checkpoint 列表 |
| `verification_results.jsonl` | 扁平化 verification result 列表 |
| `dependency_sets.jsonl` | 扁平化 dependency set 列表 |
| `perturbation_responses.jsonl` | 扁平化 perturbation response 列表 |
| `observation_plane_build_report.json` | 构建报告 |
| `observation_plane_validation_report.json` | 验证报告 |

---

## 4. Observation Plane JSONL 结构

```json
{
  "sample_id": "q000001",
  "protocol_hash": "cfbcf952...",
  "observation_plane": [
    {
      "p": {"sample_id": "...", "checkpoint_id": "...", "t": 1, ...},
      "v": [{"rule_id": "...", "rule_type": "syntax", "passed": true, ...}],
      "E_minus": ["q000001::cp::0000"],
      "R": [{"perturbed_predecessor_id": "...", "perturbation_family": "...", ...}]
    }
  ],
  "leakage_check": {
    "future_checkpoint_used": false,
    "tau_used": false,
    "final_label_used": false,
    "horizon_label_used": false,
    "downstream_feature_used": false
  }
}
```

---

## 5. p/v/E_minus/R 对齐规则

1. 每个 checkpoint 生成一个 ObservationRecord
2. `p` = Checkpoint
3. `v` = 当前 checkpoint_id 对应的 VerificationResult 列表
4. `E_minus` = 当前 checkpoint_id 对应 DependencySet.E_minus
5. `R` = 当前 checkpoint_id 对应的 PerturbationResponse 列表
6. record 顺序按 `p.t` 升序
7. 若某 checkpoint 无 verification results: `v=[]`
8. 若某 checkpoint 无 DependencySet: `E_minus=[]`
9. 若某 checkpoint 无 perturbation responses: `R=[]` (允许，特别是 E_minus=[] 的 t=1 checkpoint)

---

## 6. E_minus 历史边界

- 只包含历史 checkpoint (predecessor_t < current_t)
- 不包含当前 checkpoint
- 不包含未来 checkpoint
- 不包含不存在 checkpoint
- 如果无法确定依赖，E_minus=[]

---

## 7. R 的 predecessor 约束

- `R.perturbed_predecessor_id` 必须属于当前 record.E_minus
- `predecessor_t < current_t`
- 否则 raise ValueError

---

## 8. Leakage Boundary

- 不含 future checkpoint
- 不含 tau_i
- 不含 final_label
- 不含 horizon labels (y_i_t_h)
- 不含 downstream features (A_i_t, H_i_t, I_plus, I_minus, rho, x_dir, x_res)
- leakage_check 全部为 false

---

## 9. Unverifiable Policy

- unverifiable 只保留在 v 或 R 的 verification summary 中
- 不当作失败
- verification_changed 仅比较离散规则结果 (passed/unverifiable/message)

---

## 10. 删除或未实现内容

| 内容 | 原因 |
|------|------|
| A/H feature | 属于 §3.3，禁止迁移 |
| I+/I-/rho | 属于 §3.3，禁止迁移 |
| Recursive state | 属于 §3.4，禁止迁移 |
| Training | 属于 §3.4，禁止迁移 |
| Calibration | 属于 §3.5，禁止迁移 |
| Threshold | 属于 §3.5，禁止迁移 |
| Visualization | 属于 §4.x，禁止迁移 |

---

## 11. 命令行复现方式

```bash
# 构建观测平面 (preview mode)
python experiments/build_observation_plane.py \
  --input D:\SL-RDAF\data\data \
  --output D:\SL-RDAF\artifacts\observation_plane \
  --protocol D:\SL-RDAF\FROZEN_PROTOCOL_MANIFEST.json \
  --source-mode preview \
  --limit 5

# 验证观测平面
python experiments/validate_observation_plane.py \
  --input D:\SL-RDAF\artifacts\observation_plane\observation_planes.jsonl \
  --schemas D:\SL-RDAF\schemas \
  --manifest D:\SL-RDAF\FROZEN_PROTOCOL_MANIFEST.json

# 构建观测平面 (dataset mode)
python experiments/build_observation_plane.py \
  --input D:\SL-RDAF\data\data \
  --output D:\SL-RDAF\artifacts\observation_plane \
  --protocol D:\SL-RDAF\FROZEN_PROTOCOL_MANIFEST.json \
  --source-mode dataset \
  --limit 5
```

---

## 12. Preview Mode 与 Dataset Mode 区别

| 特性 | Preview Mode | Dataset Mode |
|------|-------------|-------------|
| 数据来源 | artifacts/observation_debug/ 下的 preview 文件 | --input 指向的数据集 |
| 是否重新计算 | 否，直接读取 preview 结果 | 是，调用 build_observation_plane() |
| 速度 | 快 | 慢 |
| 用途 | 验证组装逻辑 | 完整构建 |

---

## 13. 后续 Prompt 9 的清理建议

1. 确认 dataset mode 完整实现
2. 优化 verification rules 对 predecessor perturbation 的感知
3. 添加更多 edge case 测试
4. 完善 schema 验证
5. 生成最终提交包

---

**文档完成时间**: 2026-06-03  
**状态**: ✅ 完成
