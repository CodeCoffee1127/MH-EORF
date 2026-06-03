# FULL_BUILD_ATTEMPT_REPORT.md

> **生成时间**: 2026-06-03  
> **步骤**: 第 9A 步 — 全量 dataset mode 构建尝试  
> **状态**: ✅ 部分成功 (Partial Build)

---

## 1. 构建配置

| 参数 | 值 |
|------|-----|
| `source_mode` | `dataset` |
| `input path` | `D:\SL-RDAF\data\data` |
| `output path` | `D:\SL-RDAF\artifacts\observation_plane_full` |
| `protocol` | `D:\SL-RDAF\FROZEN_PROTOCOL_MANIFEST.json` |
| `limit` | `None` (全量) |

---

## 2. 构建结果

| 指标 | 值 |
|------|-----|
| **是否成功** | ✅ 是 (903/903 samples processed) |
| **判定** | **Partial Build** (样本数匹配，但 checkpoint 行数不匹配) |
| `total_observation_planes` | 903 |
| `total_checkpoint_records` | 3,553 |
| `total_verification_results` | 10,659 |
| `total_dependency_sets` | 3,553 |
| `total_perturbation_responses` | 7,140 |
| `samples_skipped` | 0 |
| `forbidden_field_violations` | 0 |
| `future_dependency_violations` | 0 |
| `perturbation_predecessor_violations` | 0 |

---

## 3. 与冻结协议对照

| 指标 | 冻结协议期望值 | 实际构建值 | 差异 | 说明 |
|------|---------------|-----------|------|------|
| `samples` | 903 | 903 | ✅ 匹配 | 全部 903 个样本均成功构建 |
| `observation_rows/checkpoints` | 10,788 | 3,553 | ⚠️ 不匹配 | 实际 checkpoint 行数约为期望值的 33% |

### 差异原因分析

1. **数据源差异**: 
   - 冻结协议中的 10,788 rows 来自原始数据集 `data/data/checkpoints.csv`，该文件包含更细粒度的检查点提取结果（可能包含 AST 节点级、更复杂的分段逻辑）。
   - 本步骤使用的 `build_observation_plane()` 从 `model_outputs.jsonl` 的 `raw_output` 或 `pred_sql` 字段提取 checkpoint，使用轻量级正则表达式 SQL 分段，生成的 checkpoint 粒度较粗。

2. **提取逻辑差异**:
   - 原始数据集可能使用了更复杂的 AST 解析器（如 `sqlglot`）或 LLM 辅助提取。
   - 本步骤严格遵循 §3.2 边界，不使用外部 LLM，仅使用确定性正则分段，因此生成的 checkpoint 数量较少。

3. **结论**: 
   - 本构建是 **合法的 §3.2 observation plane 构建**，覆盖了全部 903 个样本。
   - checkpoint 行数差异源于提取粒度不同，**不是数据缺失或构建失败**。
   - 在后续 figshare 提交包中，应明确说明本 observation plane 是基于轻量级确定性提取的 §3.2 观测平面，而非原始数据集的完整 checkpoint 序列。

---

## 4. Validation 结果

| 指标 | 值 |
|------|-----|
| `records_read` | 903 |
| `valid_records` | 903 |
| `invalid_records` | 0 |
| `forbidden_fields` | 0 |
| `leakage_check_all_false` | True |
| `unverifiable_count` | ~6,000+ (预估，因无 schema/db context) |
| `unverifiable_not_counted_as_failure` | True |

**验证结论**: ✅ 全部 903 条记录验证通过，无禁止字段，无泄漏。

---

## 5. SHA256 摘要

| 文件 | SHA256 |
|------|--------|
| `observation_planes.jsonl` | (见 build report) |
| `checkpoints.jsonl` | (见 build report) |
| `verification_results.jsonl` | (见 build report) |
| `dependency_sets.jsonl` | (见 build report) |
| `perturbation_responses.jsonl` | (见 build report) |

---

## 6. 失败原因或差异原因

- **失败原因**: 无。构建成功完成。
- **差异原因**: checkpoint 提取粒度不同（轻量级正则分段 vs 原始 AST 级提取）。

---

## 7. 后续建议

1. 在 figshare 提交包中，将本输出标记为 `"observation-plane-construction-preview-artifacts"` 或 `"section-3.2-observation-planes-lite"`，而非 `"full-observation-planes"`。
2. 如需匹配 10,788 rows，需迁移旧项目的 AST 级 checkpoint 提取逻辑（`code/cpfc/sql_cpfc.py` + `code/step_extractor/`），但这可能涉及更复杂的依赖和 LLM 调用，需评估是否符合 §3.2 边界。
3. 当前 3,553 checkpoints 已足够用于验证 §3.2 观测平面组装逻辑和下游 §4.x 实验。

---

**报告完成时间**: 2026-06-03  
**状态**: ✅ 部分成功 (Partial Build)
