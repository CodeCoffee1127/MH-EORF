# PROTOCOL_FREEZE_REPORT.md

> **生成时间**: 2026-06-03  
> **步骤**: 第 2 步 — 冻结协议清单与参数冲突修正方案  
> **审计依据**: MIGRATION_AUDIT.md, migration_candidates.json

---

## 1. 本步骤读取的文件清单

### 1.1 审计输入文件
- `D:\SL-RDAF\MIGRATION_AUDIT.md` — 只读审计报告
- `D:\SL-RDAF\migration_candidates.json` — 候选文件清单

### 1.2 新项目配置文件（只读复核）
- `D:\SL-RDAF\outputs\training\train_config_frozen.json` — 训练冻结配置（seed: 20260528）
- `D:\SL-RDAF\Material\SL-RDAF_algorithm_framework_phase1_phase2_phase3.md` — 算法框架文档（split: 324/214/365）
- `D:\SL-RDAF\Material\SL-RDAF 实验设计方案.md` — 实验设计方案（split: 320/214/369，注意与算法框架文档的 324/214/365 有细微差异）
- `D:\SL-RDAF\data\原始数据\dataset_warning_fixed\README_dataset_v1.0.md` — 数据集文档（total: 903 samples）
- `D:\SL-RDAF\outputs\diagnostics_4_2\agent_cluster_package\README_for_agent_cluster.md` — Agent 集群包文档（total: 903 samples, 10788 rows）

### 1.3 旧项目配置文件（只读复核）
- `D:\SL-RDAF\Material\ExternalFalsifiableMeasurementforSubmission\configs\experiment_config.yaml` — 实验配置（llm: qwen-turbo, n_candidates_per_step: 30, inject_ratio: 0.2）
- `D:\SL-RDAF\Material\ExternalFalsifiableMeasurementforSubmission\configs\frozen_manifest_v1.0.yaml` — 冻结参数清单（random_seed: 42, train_test_split: [214, 320]）
- `D:\SL-RDAF\Material\ExternalFalsifiableMeasurementforSubmission\code\verifier\constraint_rules.py` — 约束规则库（SHA256: 72b341a9...）
- `D:\SL-RDAF\Material\ExternalFalsifiableMeasurementforSubmission\code\verifier\vsp_verifier.py` — VSP 验证器（SHA256: 0cb79132...）
- `D:\SL-RDAF\Material\ExternalFalsifiableMeasurementforSubmission\code\generation\candidate_generator.py` — 候选生成器（SHA256: 36acc45c...）
- `D:\SL-RDAF\Material\ExternalFalsifiableMeasurementforSubmission\code\step_extractor\*.py` — 检查点提取器（5 文件）
- `D:\SL-RDAF\Material\ExternalFalsifiableMeasurementforSubmission\code\cpfc\*.py` — CPFC 核心（3 文件）

### 1.4 未找到的文件
- `D:\SL-RDAF` 下未找到明确指定 LLM 版本的配置文件
- `D:\SL-RDAF` 下未找到 verification repeats / N / M 的定义
- `D:\SL-RDAF` 下未找到完整的 perturbation family 定义
- `D:\SL-RDAF` 下未找到 rule_library 版本号

---

## 2. 已冻结参数

| 参数 | 最终值 | 状态 | 来源 |
|------|--------|------|------|
| `temperature` | `0` | `frozen` | 论文 §3.2 要求 |
| `random_seed` | `20260528` | `frozen_or_audit_confirmed` | `outputs/training/train_config_frozen.json` |
| `split.train_dev.samples` | `324` | `frozen` | `Material/SL-RDAF_algorithm_framework_phase1_phase2_phase3.md` |
| `split.train_dev.rows` | `3928` | `frozen` | 同上 |
| `split.cal_dev.samples` | `214` | `frozen` | 同上 |
| `split.cal_dev.rows` | `2571` | `frozen` | 同上 |
| `split.heldout.samples` | `365` | `frozen` | 同上 |
| `split.heldout.rows` | `4289` | `frozen` | 同上 |
| `split.total_samples` | `903` | `frozen` | `data/原始数据/dataset_warning_fixed/README_dataset_v1.0.md` |
| `split.total_observation_rows` | `10788` | `frozen` | `outputs/diagnostics_4_2/agent_cluster_package/README_for_agent_cluster.md` |
| `observation_boundary.leakage_policy` | `fail_closed` | `frozen` | 审计决策 |

---

## 3. 冲突参数及解决

| 参数 | 旧值 | 新值 | 解决策略 |
|------|------|------|---------|
| `random_seed` | `42` | `20260528` | 采用新值（SL-RDAF 最终训练冻结种子） |
| `split policy` | `[214, 320]` | `{train_dev: 324/3928, cal_dev: 214/2571, heldout: 365/4289}` | 采用新值（三元划分） |
| `temperature` | 未冻结 | `0` | 显式冻结为 0（论文要求） |

---

## 4. 缺失参数

| 参数 | 状态 | 说明 |
|------|------|------|
| `llm_version` | `requires_confirmation` | 旧项目为 qwen-turbo，但 SL-RDAF 未确认；不得直接采用 |
| `rule_library_version` | `derived_provenance_only_requires_confirmation` | 无显式版本号；使用 SHA256 provenance ID |
| `perturbation_family_version` | `incomplete_requires_confirmation` | 仅有 inject_ratio=0.2；缺少完整定义 |
| `verification_repeats` | `requires_confirmation` | 两项目均未找到明确定义 |
| `N` | `requires_confirmation` | 两项目均未找到明确定义 |
| `M` | `requires_confirmation` | 两项目均未找到明确定义 |

---

## 5. Derived Provenance Hash 说明

### 5.1 规则库 Provenance

由于旧项目 `constraint_rules.py` 和 `vsp_verifier.py` 无显式版本号，使用文件 SHA256 前 12 位作为可追溯 ID：

- **Provenance ID**: `legacy_rules_sha256_72b341a9063d`
- **constraint_rules.py SHA256**: `72b341a9063d8ae76ea06d4ee3a0a260f9482b9908eaca04e4e4ac74776958f3`
- **vsp_verifier.py SHA256**: `0cb791325e3479cc0feb7cd47db0713696a44817c944b230ce989222d3ab72a2`

**注意**: 此 provenance ID 仅用于可追溯性跟踪，**不是**论文声明的版本号。

### 5.2 扰动族 Provenance

由于旧项目仅有 `inject_ratio=0.2`，缺少完整扰动族定义，使用 `candidate_generator.py` 的 SHA256 前 12 位：

- **Provenance ID**: `legacy_perturbation_sha256_36acc45cf00a`
- **candidate_generator.py SHA256**: `36acc45cf00a2c588d64e4c297b2379c1a5e142e70b7e48306293ba1973bc093`

**注意**: 此 provenance ID 仅用于可追溯性跟踪，**不是**完整的扰动族定义。

---

## 6. 不能自动确认的人工复核问题

### 6.1 必须人工确认

1. **`llm_version`**: 
   - 问题: SL-RDAF 使用的 LLM 版本是什么？
   - 旧项目值: `qwen-turbo`
   - 影响: 如果原始 trace 缺失，需要调用 LLM 重新生成；必须确认最终模型版本
   - 建议: 查阅 SL-RDAF 论文 §3.1 或 §4.1 实验设置

2. **`verification_repeats`**:
   - 问题: 论文 §3.2 中 verification repeats 的固定值是多少？
   - 影响: 影响验证结果的稳定性和计算成本
   - 建议: 查阅 SL-RDAF 论文 §3.2 验证规则引擎部分

3. **`N` 和 `M`**:
   - 问题: 论文 §3.2 中 N（验证重复次数）和 M（扰动次数）的固定值是多少？
   - 影响: 影响扰动响应记录的完整性和计算成本
   - 建议: 查阅 SL-RDAF 论文 §3.2 扰动响应记录部分

4. **`perturbation_family_version`**:
   - 问题: 完整的扰动族定义是什么？
   - 旧项目部分定义: `inject_ratio: 0.2`
   - 影响: 影响扰动响应记录的可复现性
   - 建议: 查阅 SL-RDAF 论文 §3.2 或 §3.1 扰动定义部分

5. **`rule_library_version`**:
   - 问题: 是否需要为规则库分配显式版本号？
   - 当前方案: 使用 SHA256 provenance ID
   - 影响: 影响规则库变更追踪
   - 建议: 如果论文有声明版本号，优先采用论文版本

### 6.2 数据划分差异说明

在复核过程中发现两个来源文件的样本数有细微差异：

| 来源 | train-dev | cal-dev | heldout | 总样本 |
|------|-----------|---------|---------|--------|
| `SL-RDAF 实验设计方案.md` | 320 | 214 | 369 | 903 |
| `SL-RDAF_algorithm_framework_phase1_phase2_phase3.md` | 324 | 214 | 365 | 903 |
| `README_dataset_v1.0.md` | - | 534 (calibration) | 369 | 903 |
| `README_for_agent_cluster.md` | 324 | 214 | 365 | 903 |

**采用值**: `train-dev: 324, cal-dev: 214, heldout: 365`（来自算法框架文档和 agent 集群包文档，为最新执行结果）

**待确认**: 实验设计方案中的 320/214/369 是否为早期规划值，已被实际执行的 324/214/365 取代？

---

## 7. 对后续迁移步骤的约束

### 7.1 严格禁止

以下行为在后续迁移步骤中**严格禁止**：

1. ❌ **不得调用 LLM**，除非用户确认 `llm_version` 且原始 trace 缺失
2. ❌ **不得把 `qwen-turbo` 写成 SL-RDAF 最终 LLM**，必须保持 `null` 直到用户确认
3. ❌ **不得把 `n_candidates_per_step=30` 写成 N/M**，这是 VSP 候选生成参数，不是 verification repeats
4. ❌ **不得引入 §3.3 或 §3.4 字段**，包括：
   - `A_i_t`, `H_i_t`, `I_plus`, `I_minus`, `rho`（诊断特征工程）
   - `x_dir`, `x_res`（模型输入）
   - `s_i_t`（递推状态）
   - 校准映射 `f_k`、阈值 `θ_h`
5. ❌ **不得读取以下信息**（数据泄漏防护）：
   - `tau_i`（首次退化时间）
   - `final_label`（最终执行标签）
   - `endpoint_accuracy`（端点准确率）
   - `execution_accuracy`（执行准确率）
   - `y_i_t_h`（多视野标签）
   - `calibrated_risk`（校准风险）
   - `model_prediction`（模型预测）
   - `heldout_metric`（heldout 指标）
6. ❌ **不得修改旧项目文件** `D:\SL-RDAF\Material\ExternalFalsifiableMeasurementforSubmission\` 中的任何内容

### 7.2 必须遵守

以下规则在后续迁移步骤中**必须遵守**：

1. ✅ **依赖集合 E_minus 只能包含历史 checkpoint**，不能包含未来信息
2. ✅ **perturbation response 只记录响应**，不计算 I_plus/I_minus 或特征
3. ✅ **所有随机操作使用 seed=20260528**
4. ✅ **所有 LLM 调用使用 temperature=0**（如果调用）
5. ✅ **观测平面输出使用论文符号**：`checkpoint`, `observation_plane`, `verification_result`, `dependency_set`, `perturbation_response`, `E_minus`, `R`
6. ✅ **所有输出保留可追溯记录**：生成 `observation_plane_build_report.json` 和 `observation_plane_validation_report.json`

### 7.3 观测平面边界

```
允许使用的信息:
  ✓ 当前检查点 p_i,t
  ✓ 历史检查点 p_i,1:t-1
  ✓ 验证时刻可用的 schema/数据库信息
  ✓ 外部规则验证结果
  ✓ 前序扰动响应 R_i,t'

禁止使用的信息:
  ✗ 未来检查点 p_i,t+1:T_i
  ✗ tau_i（首次退化时间）
  ✗ final_execution_label
  ✗ endpoint_accuracy
  ✗ y_i_t_h（多视野标签）
  ✗ calibrated_risk
  ✗ model_prediction
  ✗ heldout_metric
```

---

## 8. 生成文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| FROZEN_PROTOCOL_MANIFEST.json | `D:\SL-RDAF\FROZEN_PROTOCOL_MANIFEST.json` | 主清单（含 protocol_hash） |
| frozen_protocol.json | `D:\SL-RDAF\configs\frozen_protocol.json` | 主清单的同步副本 |
| observation_protocol.yaml | `D:\SL-RDAF\configs\observation_protocol.yaml` | 人类可读配置 |
| PROTOCOL_CONFLICTS.md | `D:\SL-RDAF\PROTOCOL_CONFLICTS.md` | 冲突记录与采用策略 |
| PROTOCOL_FREEZE_REPORT.md | `D:\SL-RDAF\PROTOCOL_FREEZE_REPORT.md` | 本文件（执行证据与约束） |

---

## 9. 校验结果

### 9.1 JSON 校验
```
✅ FROZEN_PROTOCOL_MANIFEST.json 存在且可 json.load
✅ protocol_hash: cfbcf95275899c462a6694b240df3f9679a0051a061403f27e94c041c816afaf
✅ temperature: 0
✅ random_seed: 20260528
✅ splits: train_dev=324, cal_dev=214, heldout=365
✅ llm_version: null (requires_confirmation)
```

### 9.2 副本一致性
```
✅ configs/frozen_protocol.json 与 FROZEN_PROTOCOL_MANIFEST.json 一致
```

### 9.3 YAML 校验
```
✅ configs/observation_protocol.yaml 存在且可 yaml.safe_load
✅ 语义与 FROZEN_PROTOCOL_MANIFEST.json 一致
```

---

**报告完成时间**: 2026-06-03  
**执行状态**: ✅ 第 2 步完成  
**下一步**: 第 3 步 — 迁移 §3.2 核心代码（待用户确认缺失参数后执行）
