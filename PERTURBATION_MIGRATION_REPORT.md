# PERTURBATION_MIGRATION_REPORT.md

> **生成时间**: 2026-06-03  
> **步骤**: 第 7 步 — 增量迁移 perturbation response generation  
> **状态**: ✅ 完成

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/slrdaf/observation/perturbations.py` | 增量更新 | 实现 4 个扰动族及 public API |
| `experiments/preview_perturbation_responses.py` | 新建 | Perturbation preview 脚本 |
| `tests/test_perturbation_responses.py` | 新建 | 12 个测试用例 |
| `docs/migration_perturbation_responses.md` | 新建 | 迁移文档 |
| `PERTURBATION_MIGRATION_REPORT.md` | 新建 | 本文件 |

---

## 2. 旧项目来源文件清单

| 文件 | 路径 | 用途 |
|------|------|------|
| `candidate_generator.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/generation/` | 候选多样性生成 |
| `experiment_config.yaml` | `Material/ExternalFalsifiableMeasurementforSubmission/configs/` | 实验配置 |
| `frozen_manifest_v1.0.yaml` | `Material/ExternalFalsifiableMeasurementforSubmission/configs/` | 冻结参数 |
| `schema.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/step_extractor/` | 数据结构 |
| `vsp_verifier.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/verifier/` | 验证器 |
| `constraint_rules.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/verifier/` | 约束规则 |

---

## 3. 迁移函数清单

| 函数 | 类型 | 说明 |
|------|------|------|
| `load_perturbation_families()` | 公开 | 加载 4 个确定性扰动族 |
| `perturb_checkpoint()` | 公开 | 对前驱 checkpoint 应用扰动 |
| `generate_perturbation_responses()` | 公开 | 生成所有 checkpoint 的扰动响应 |
| `hash_perturbation_payload()` | 公开 | 计算 payload SHA256 |
| `_perturb_identifier_mask()` | 内部 | identifier mask 扰动 |
| `_perturb_operator_flip()` | 内部 | operator flip 扰动 |
| `_perturb_numeric_value()` | 内部 | numeric value shift 扰动 |
| `_perturb_clause_marker_noise()` | 内部 | clause marker noise 扰动 |
| `_extract_checkpoint_text()` | 内部 | 提取 checkpoint 文本 |
| `_deterministic_choice()` | 内部 | 确定性选择 |
| `_summarize_perturbation_payload()` | 内部 | 生成 payload 安全摘要 |
| `_normalize_verification_summary()` | 内部 | 归一化验证结果摘要 |
| `_build_checkpoint_lookup()` | 内部 | 构建 checkpoint 查找表 |
| `_get_dependency_set_for_checkpoint()` | 内部 | 查找 DependencySet |

---

## 4. Perturbation Family 清单

| family_id | family_type | description | version |
|-----------|-------------|-------------|---------|
| `structural.identifier_mask` | structural | Mask one identifier token | implementation_draft_for_section_3_2 |
| `structural.operator_flip` | structural | Flip comparison/operator token | implementation_draft_for_section_3_2 |
| `numerical.value_shift` | numerical | Shift numeric literal by offset | implementation_draft_for_section_3_2 |
| `structural.clause_marker_noise` | structural | Safe clause-marker perturbation | implementation_draft_for_section_3_2 |

---

## 5. E_minus 约束检查结果

- ✅ 只扰动 E_minus 中的历史 predecessor
- ✅ 不扰动当前 checkpoint
- ✅ 不扰动 future checkpoint
- ✅ 对 E_minus=[] 的 checkpoint 不生成 response
- ✅ 所有 perturbed_predecessor_id 属于对应 checkpoint 的 E_minus
- ✅ predecessor_t < target_t

---

## 6. Before/After Verification Summary 结构

```json
{
  "rule_id": "syntax.sql_fragment_parseable",
  "rule_type": "syntax",
  "passed": true,
  "unverifiable": false,
  "message": "Syntax validation passed"
}
```

- 只包含离散规则摘要
- 不包含 A_i_t、H_i_t、score、feature

---

## 7. Payload Hash 策略

- 使用 `hash_perturbation_payload(payload)` 计算 SHA256
- 长度 64 字符
- 不保存完整 payload 原文
- PerturbationResponse 中只保存 `perturbation_payload_hash` 和 `safe_summary`

---

## 8. Preview 结果

```
Samples attempted: 5
Samples succeeded: 5
Samples skipped: 0
Total perturbation responses: 52

Responses by family:
  structural.identifier_mask: 13
  structural.operator_flip: 13
  numerical.value_shift: 13
  structural.clause_marker_noise: 13

Changed predecessor: 32
Verification changed: 0
Unchanged/no effect: 52

Invalid/future predecessor violations: 0
Payload hashes unique: true
Deterministic replay SHA256 match: true
  First run:  482d915c43461d88252e0341bef195a6d76d28bc518b303e5a05e6afdab476b8
  Second run: 482d915c43461d88252e0341bef195a6d76d28bc518b303e5a05e6afdab476b8
```

---

## 9. 测试结果

```
$ pytest tests -q
......................................................                   [100%]
54 passed in 0.07s
```

**测试覆盖**:
- ✅ 第 3 步原有 16 个测试全部通过
- ✅ 第 4 步新增 6 个 checkpoint extraction 测试全部通过
- ✅ 第 5 步新增 10 个 verification rules 测试全部通过
- ✅ 第 6 步新增 10 个 dependency extraction 测试全部通过
- ✅ 第 7 步新增 12 个 perturbation responses 测试全部通过

---

## 10. py_compile 结果

```
$ python -m py_compile perturbations.py preview_perturbation_responses.py
```

**所有文件编译通过，无语法错误。**

---

## 11. 禁止符号扫描结果

在 `perturbations.py` 中搜索下游字段：
```
A_i_t, H_i_t, I_plus, I_minus, Inec, rho, risk_memory, dependency_weight, 
c_i_j_to_t, w_i_j_to_t, x_dir, x_res, s_i_t, Q_i_t_h, tau_i, final_label, 
endpoint_accuracy, execution_accuracy, train, fit, predict, 
calibration, threshold, plot, matplotlib, seaborn, Beta, entropy, score, feature
```

**结果**: 无匹配。✅ 通过

---

## 12. 是否修改旧项目文件

**否**。本步骤仅读取旧项目文件作为参考，未修改任何旧项目文件。

---

## 13. 后续 Prompt 8 的建议输入文件

| 文件 | 路径 | 用途 |
|------|------|------|
| Checkpoint Preview | `artifacts/observation_debug/checkpoint_sequence_preview.jsonl` | 提供 checkpoint 序列 |
| Verification Preview | `artifacts/observation_debug/verification_preview.jsonl` | 提供验证结果 |
| Dependency Preview | `artifacts/observation_debug/dependency_sets_preview.jsonl` | 提供 E_minus 约束 |
| Perturbation Preview | `artifacts/observation_debug/perturbation_response_preview.jsonl` | 提供 R_{i,t} 扰动响应 |
| Perturbation Report | `artifacts/observation_debug/perturbation_response_preview_report.json` | 了解扰动分布 |
| Perturbations.py | `src/slrdaf/observation/perturbations.py` | 提供 PerturbationResponse dataclass 定义 |
| Protocol | `FROZEN_PROTOCOL_MANIFEST.json` | 提供 protocol_hash 和配置 |

---

## 14. 验收标准检查

| # | 验收标准 | 状态 |
|---|---------|------|
| 1 | `load_perturbation_families` 返回至少 4 个 deterministic families | ✅ 通过 |
| 2 | `perturb_checkpoint` 不再 raise NotImplementedError | ✅ 通过 |
| 3 | `generate_perturbation_responses` 不再 raise NotImplementedError | ✅ 通过 |
| 4 | `hash_perturbation_payload` 原有测试继续通过 | ✅ 通过 |
| 5 | 只扰动 E_minus 中的历史 predecessor | ✅ 通过 |
| 6 | 不扰动当前 checkpoint | ✅ 通过 |
| 7 | 不扰动 future checkpoint | ✅ 通过 |
| 8 | 对 E_minus=[] 的 checkpoint 不生成 response | ✅ 通过 |
| 9 | 每条 PerturbationResponse 符合 schema | ✅ 通过 |
| 10 | perturbation_payload_hash 长度 64 | ✅ 通过 |
| 11 | before/after 只含离散规则摘要，不含 A/H/score/feature | ✅ 通过 |
| 12 | 不计算 A_i_t、H_i_t、c_i_j_to_t、w_i_j_to_t、I_plus、I_minus、rho | ✅ 通过 |
| 13 | 不使用 tau_i、final_label、endpoint_accuracy、y_i_t_h | ✅ 通过 |
| 14 | unverifiable=True 不被解释为 failed dependency | ✅ 通过 |
| 15 | 第 3/4/5/6 步已有测试继续通过 | ✅ 通过 (54/54) |
| 16 | 新增 perturbation tests 通过 | ✅ 通过 (12/12) |
| 17 | py_compile 通过 | ✅ 通过 |
| 18 | 不修改旧项目文件 | ✅ 通过 |
| 19 | 不调用 LLM | ✅ 通过 |
| 20 | 运行两次 preview，核心输出 SHA256 一致 | ✅ 通过 |
| 21 | 能生成 perturbation preview JSONL 和 report | ✅ 通过 |
| 22 | 生成 migration 文档和执行报告 | ✅ 通过 |
| 23 | pytest 通过 | ✅ 通过 (54/54) |

---

**报告完成时间**: 2026-06-03  
**执行状态**: ✅ 第 7 步完成  
**下一步**: Prompt 8 — 完整观测平面组装与 CLI 实现
