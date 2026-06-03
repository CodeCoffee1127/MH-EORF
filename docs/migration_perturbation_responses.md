# Migration: Perturbation Responses

> **创建时间**: 2026-06-03  
> **步骤**: 第 7 步 — 增量迁移 perturbation response generation  
> **状态**: ✅ 完成

---

## 1. 本步骤迁移目标

实现 `D:\SL-RDAF\src\slrdaf\observation\perturbations.py` 中的：
- `load_perturbation_families()` — 加载 4 个确定性扰动族
- `perturb_checkpoint()` — 对前驱 checkpoint 应用扰动
- `generate_perturbation_responses()` — 生成所有 checkpoint 的扰动响应 R_{i,t}

本步骤只生成 PerturbationFamily、PerturbationResponse、R_{i,t}，不生成 §3.3 扰动特征或依赖风险特征。

---

## 2. 旧项目来源文件

| 旧项目文件 | 用途 | 迁移状态 |
|-----------|------|---------|
| `code/generation/candidate_generator.py` | 候选多样性生成 | ✅ 已阅读，参考错误注入逻辑 |
| `configs/experiment_config.yaml` | 实验配置 | ✅ 已参考 |
| `configs/frozen_manifest_v1.0.yaml` | 冻结参数 | ✅ 已参考 |
| `code/step_extractor/schema.py` | 数据结构 | ✅ 已参考 |
| `code/verifier/vsp_verifier.py` | 验证器 | ✅ 已参考 |
| `code/verifier/constraint_rules.py` | 约束规则 | ✅ 已参考 |

---

## 3. 新项目目标文件

| 新文件 | 状态 |
|--------|------|
| `src/slrdaf/observation/perturbations.py` | ✅ 已增量更新 |
| `experiments/preview_perturbation_responses.py` | ✅ 已创建 |
| `tests/test_perturbation_responses.py` | ✅ 已创建 (12 个测试) |
| `artifacts/observation_debug/perturbation_response_preview.jsonl` | ✅ 已生成 |
| `artifacts/observation_debug/perturbation_response_preview_report.json` | ✅ 已生成 |
| `docs/migration_perturbation_responses.md` | ✅ 已创建 |

---

## 4. Perturbation Family 列表

| family_id | family_type | description | deterministic |
|-----------|-------------|-------------|---------------|
| `structural.identifier_mask` | structural | Mask one identifier token in predecessor checkpoint text | ✅ true |
| `structural.operator_flip` | structural | Flip a local comparison/operator token when present | ✅ true |
| `numerical.value_shift` | numerical | Shift one numeric literal by a deterministic small offset | ✅ true |
| `structural.clause_marker_noise` | structural | Apply a safe local clause-marker perturbation | ✅ true |

**版本标记**: `implementation_draft_for_section_3_2` (非正式论文版本)

---

## 5. Deterministic Perturbation 策略

- 不使用随机全局状态
- 如需选择 token，使用 `deterministic_choice(seed_material = protocol_hash + checkpoint_id + family_id)`
- 不调用 `random.random()`，除非先用 `protocol.random_seed + stable hash` 创建局部 `random.Random`
- 不引入非确定性
- 不改变原始 checkpoint 对象，只返回 perturbation payload
- payload 中不保存敏感原文，完整扰动内容只可临时用于验证，最终 PerturbationResponse 中只保存 hash 和 summary

---

## 6. E_minus 约束

- **只能扰动历史 predecessor** (predecessor_t < target_t)
- **不扰动当前 checkpoint**
- **不扰动 future checkpoint**
- **不扰动不在 E_minus 中的 checkpoint**
- 如果 E_minus=[]，则该 checkpoint 没有 perturbation response

---

## 7. Before/After Verification Summary 语义

### Before Verification
- 使用 context 中 verification_results 中 target checkpoint 的原始验证结果摘要
- 如果 context 中无 verification_results，则现场调用 verify_checkpoint
- 摘要只包含：rule_id, rule_type, passed, unverifiable, message
- **不计算** pass rate、A_i_t、H_i_t

### After Verification
- 构造"扰动后的局部上下文"：不改变 target checkpoint 本身
- 只在 context 中记录 perturbed_predecessor_summary
- 对 target checkpoint 重新调用 verify_checkpoint
- 如果当前 verification 规则无法感知 predecessor perturbation，after_verification 可能与 before 相同，这是允许的
- response_summary 中记录 changed=false 或 verification_changed=false

### Verification Changed 判断
- 只比较 before_verification 和 after_verification 的离散规则结果
- 允许比较：rule_id, rule_type, passed, unverifiable, message
- **禁止**比较或计算：pass count, pass ratio, A_i_t, H_i_t, entropy, consistency, risk, weights
- verification_changed=True 当且仅当至少一条 rule 的 passed/unverifiable/message 出现变化

---

## 8. Payload Hash 与敏感信息保护

- 使用 `hash_perturbation_payload(payload)` 计算 SHA256
- 长度 64 字符
- 不保存完整 payload 原文
- PerturbationResponse 中只保存 `perturbation_payload_hash` 和 `safe_summary`
- 完整扰动内容只可临时用于验证

---

## 9. 删除或未迁移逻辑

| 逻辑 | 原因 |
|------|------|
| Repeated verification frequency | 属于 §3.3，禁止迁移 |
| Beta smoothing | 属于 §3.3，禁止迁移 |
| A_i_t / H_i_t | 属于 §3.3 诊断特征，禁止迁移 |
| c_i_j_to_t | 属于 §3.3 依赖权重，禁止迁移 |
| Dependency weight | 属于 §3.3，禁止迁移 |
| I_plus / I_minus | 属于 §3.3，禁止迁移 |
| rho / risk memory | 属于 §3.3，禁止迁移 |
| Diagnostic features | 属于 §3.3，禁止迁移 |
| Training/calibration/visualization | 属于 §3.4/§4.x，禁止迁移 |
| LLM 调用 | 本步骤不调用 LLM，使用确定性扰动 |

---

## 10. Preview 结果摘要

```
Samples succeeded: 5/5
Total responses: 52
Changed predecessor: 32
Verification changed: 0
Unchanged/no effect: 52

Families:
  structural.identifier_mask: 13
  structural.operator_flip: 13
  numerical.value_shift: 13
  structural.clause_marker_noise: 13

Deterministic replay SHA256 match: true
  First run:  482d915c43461d88252e0341bef195a6d76d28bc518b303e5a05e6afdab476b8
  Second run:  482d915c43461d88252e0341bef195a6d76d28bc518b303e5a05e6afdab476b8
```

**说明**:
- verification_changed=0 是因为当前验证规则不感知 predecessor perturbation
- 这是预期行为，verification 规则将在后续优化
- SHA256 一致证明确定性

---

## 11. 与 Prompt 8 的接口

### 11.1 Perturbation Responses 作为观测平面组成部分

- `perturbation_response_preview.jsonl` 将作为观测平面 O_i 中 R_{i,t} 的来源
- Prompt 8 只组装，不计算特征
- R_{i,t} 仅包含针对 E_minus 中 predecessor 的扰动响应

### 11.2 约束

- Prompt 8 不得计算 A_i_t、H_i_t、I_plus、I_minus、rho
- Prompt 8 不得引入 §3.3/§3.4 字段
- Prompt 8 仅组装 O_i = {(p_{i,t}, v_{i,t}, E_minus_{i,t}, R_{i,t})}

---

**文档完成时间**: 2026-06-03  
**状态**: ✅ 迁移完成
