# PROTOCOL_CONFLICTS.md

> **生成时间**: 2026-06-03  
> **步骤**: 第 2 步 — 冻结协议清单与参数冲突修正方案  
> **审计依据**: MIGRATION_AUDIT.md, migration_candidates.json

---

## 参数冲突与采用策略

| 参数 | SL-RDAF 最终值 | 旧项目值 | 状态 | 采用值 | 证据文件 | 处理理由 |
|------|---------------|---------|------|--------|---------|---------|
| `temperature` | `0` | 未冻结 | `frozen` | `0` | 论文 §3.2 要求 | 旧项目未显式冻结 temperature；SL-RDAF 要求确定性生成，必须为 0 |
| `random_seed` | `20260528` | `42` | `frozen_or_audit_confirmed` | `20260528` | `outputs/training/train_config_frozen.json` | 旧值为通用默认值；新值为 SL-RDAF 最终训练冻结种子 |
| `split policy` | `train-dev: 324/3928, cal-dev: 214/2571, heldout: 365/4289` | `[214, 320]` | `frozen` | 三元划分 | `Material/SL-RDAF_algorithm_framework_phase1_phase2_phase3.md`<br>`data/原始数据/dataset_warning_fixed/README_dataset_v1.0.md`<br>`outputs/diagnostics_4_2/agent_cluster_package/README_for_agent_cluster.md` | 旧值为二元划分（Calibration:Test）；新值为 SL-RDAF 最终三元划分（train-dev/cal-dev/heldout） |
| `llm_version` | `null` | `qwen-turbo` | `requires_confirmation` | `null` | `Material/ExternalFalsifiableMeasurementforSubmission/configs/experiment_config.yaml`（旧项目） | 旧项目使用 qwen-turbo，但 SL-RDAF 最终协议未确认；不得直接采用为 SL-RDAF 最终 LLM |
| `rule_library_version` | `null` | 无版本号 | `derived_provenance_only_requires_confirmation` | `null` + `legacy_rules_sha256_72b341a9063d` | `code/verifier/constraint_rules.py` (SHA256: `72b341a9...`)<br>`code/verifier/vsp_verifier.py` (SHA256: `0cb79132...`) | 旧项目无显式版本号；使用 SHA256 前 12 位作为可追溯 provenance ID，非论文声明版本 |
| `perturbation_family_version` | `null` | `inject_ratio: 0.2` | `incomplete_requires_confirmation` | `null` + `legacy_perturbation_sha256_36acc45cf00a` | `configs/experiment_config.yaml` (inject_ratio)<br>`code/generation/candidate_generator.py` (SHA256: `36acc45c...`) | 旧项目仅有 inject_ratio=0.2，缺少完整扰动族定义；使用 SHA256 前 12 位作为 provenance ID |
| `verification_repeats` | `null` | 未明确 | `requires_confirmation` | `null` | 无 | 两项目均未找到 verification repeats 的明确定义 |
| `N` | `null` | 未明确 | `requires_confirmation` | `null` | 无 | 两项目均未找到 N（验证重复次数）的明确定义 |
| `M` | `null` | 未明确 | `requires_confirmation` | `null` | 无 | 两项目均未找到 M（扰动次数）的明确定义 |

---

## 相关但非冲突的参数

| 参数 | 旧项目值 | 说明 | 处理方式 |
|------|---------|------|---------|
| `n_candidates_per_step` | `30` | VSP 候选生成参数 | 仅记录为 `legacy_related_values`，**不得**写成 verification repeats / N / M |
| `verification_timeout` | `30s` | 验证超时 | 可迁移至新配置，但不属于冻结协议核心参数 |
| `gate_params` | `w_A=1.436, w_u=-0.338, b_g=-5.0` | 门控参数 | 属于 §3.3/§3.4，不在 §3.2 范围内 |
| `alpha_0` | `1.4426950408889634` | 理论值 ln(2)/ln(e) | 属于 §3.4 动力学模型，不在 §3.2 范围内 |

---

## 冲突解决原则

1. **SL-RDAF 最终协议优先**：当旧项目参数与 SL-RDAF 最终协议不一致时，以 SL-RDAF 为准
2. **缺失参数不编造**：如果无法在新项目最终协议中找到明确值，保持 `null` 并标记 `requires_confirmation`
3. **Legacy 值仅作追溯**：旧项目值仅用于 provenance tracking 和冲突解决参考，不直接采用
4. **SHA256 provenance**：对于无版本号的规则库和扰动族，使用文件 SHA256 前 12 位作为可追溯 ID
5. **严格 §3.2 边界**：不引入 §3.3（诊断特征工程）、§3.4（模型训练）、calibration、threshold selection、heldout evaluation、visualization 相关参数

---

## 人工确认清单

以下参数需要用户在后续步骤中确认：

1. **`llm_version`**: SL-RDAF 使用的 LLM 版本是什么？（旧项目为 qwen-turbo，但需确认）
2. **`verification_repeats`**: 论文 §3.2 中 verification repeats 的固定值是多少？
3. **`N`**: 论文 §3.2 中 N（验证重复次数）的固定值是多少？
4. **`M`**: 论文 §3.2 中 M（扰动次数）的固定值是多少？
5. **`perturbation_family_version`**: 完整的扰动族定义是什么？（目前仅有 inject_ratio=0.2）
6. **`rule_library_version`**: 是否需要为规则库分配显式版本号？（目前使用 SHA256 provenance）

---

**冲突解决完成时间**: 2026-06-03  
**状态**: ✅ 已冻结明确参数，缺失参数标记为 requires_confirmation
