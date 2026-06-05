# STEP_MIGRATION_REPORT.md

> **生成时间**: 2026-06-03
> **步骤**: 第 4 步 — 增量迁移 step sequence construction
> **状态**: ✅ 完成

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/mhiedew/observation/steps.py` | 增量更新 | 实现 `build_step_sequence()` 及相关 helper |
| `experiments/preview_step_sequences.py` | 新建 | Preview 脚本 |
| `tests/test_step_extraction.py` | 新建 | 6 个测试用例 |
| `docs/migration_step_extractor.md` | 新建 | 迁移文档 |
| `STEP_MIGRATION_REPORT.md` | 新建 | 本文件 |

---

## 2. 旧项目来源文件清单

| 文件 | 路径 | 用途 |
|------|------|------|
| `step_extractor.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/step_extractor/` | VerifierDrivenStepExtractor 核心 |
| `segmentation.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/step_extractor/` | StructureParse 结构解析 |
| `schema.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/step_extractor/` | StepObject、ParseStatus 定义 |
| `bridge_sql_pipeline.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/step_extractor/` | SQL clause → StepObject 桥接 |
| `paper_based_step_extractor_reconstruction.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/step_extractor/` | 重构助手 |
| `sql_cpfc.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/cpfc/` | CPFC SQL 处理 |

---

## 3. 迁移函数清单

| 函数 | 类型 | 说明 |
|------|------|------|
| `build_step_sequence()` | 公开 | 主入口，从 sample dict 构建 StepSequence |
| `assign_step_ids()` | 公开 | 分配 step ID（保留第 3 步实现） |
| `_extract_sample_id()` | 内部 | 提取 sample_id，支持多字段优先级 fallback |
| `_classify_step_type()` | 内部 | 映射 step/sql 内容到 step_type |
| `_extract_sql_from_text()` | 内部 | 从 markdown 代码块或文本中提取 SQL |
| `_segment_sql_to_steps()` | 内部 | 正则表达式 SQL 子句分段 |
| `_extract_steps_from_structured_trace()` | 内部 | 从结构化 trace 提取 steps |

---

## 4. Step_type 映射表

| 输入特征 | step_type | 示例 |
|---------|----------------|------|
| SELECT 列引用 | `column_reference` | `SELECT u.name, u.age` |
| WHERE / HAVING 谓词 | `predicate_binding` | `WHERE u.age > 18` |
| FROM / JOIN 表引用 | `schema_linking` | `FROM users AS u JOIN orders AS o` |
| GROUP BY / ORDER BY / LIMIT / 聚合 | `aggregation_or_ordering` | `ORDER BY u.name LIMIT 10` |
| 无法识别 / 推理步骤文本 | `other` | `Step 1: Analyze the schema` |

---

## 5. 数据字段识别优先级

### 5.1 sample_id 提取
1. `sample_id`
2. `id`
3. `question_id`
4. `example_id`
5. `uid`
6. `db_id + index`
7. Deterministic hash (fallback)

### 5.2 Trace / SQL 提取
1. 结构化 trace: `raw_trace`, `reasoning_trace`, `agent_trace`, `trace`, `intermediate_steps`, `steps`, `generated_steps`, `model_output`, `llm_output`
2. Generated SQL: `generated_sql`, `pred_sql`, `prediction_sql`, `predicted_sql`, `output_sql`, `sql_prediction`
3. Raw output: `raw_output` (提取 ```sql 代码块 或 `Step N:` 标记)
4. Gold SQL: `gold_sql`, `gold_query`, `ground_truth_sql`, `label_sql` → **禁止使用**

---

## 6. 禁止字段处理方式

| 禁止字段 | 处理方式 |
|---------|---------|
| `final_label`, `endpoint_accuracy`, `execution_accuracy` | 从 step dict 中过滤，不写入 content/metadata |
| `tau`, `tau_i`, `y_i_t_h` | 同上 |
| `A_i_t`, `H_i_t`, `I_plus`, `I_minus`, `rho` | 同上 |
| `x_dir`, `x_res` | 同上 |
| `gold_sql` 等 | 若仅存在 gold SQL，raise ValueError 跳过样本 |

**实现位置**: `_FORBIDDEN_META_FIELDS` 集合 + `_extract_steps_from_structured_trace()` 过滤逻辑

---

## 7. Preview 结果

```
Input: D:\SL-RDAF\data\data
Files scanned: 31
Samples attempted: 5
Samples succeeded: 5
Samples skipped: 0

Step type distribution:
  schema_linking: 9
  column_reference: 5
  predicate_binding: 4
  aggregation_or_ordering: 2
  other: 1

Source field distribution:
  pred_sql: 21
```

**输出文件**:
- `artifacts/observation_debug/step_sequence_preview.jsonl`
- `artifacts/observation_debug/step_sequence_preview_report.json`

---

## 8. 测试结果

```
$ pytest tests -q
......................                                                   [100%]
22 passed in 0.09s
```

**测试覆盖**:
- ✅ 第 3 步原有 16 个测试全部通过
- ✅ 新增 6 个 step extraction 测试全部通过：
  - `test_structured_trace` — 结构化 trace 提取
  - `test_generated_sql` — Generated SQL 提取
  - `test_gold_sql_forbidden` — Gold SQL 禁用
  - `test_forbidden_fields_leakage` — 禁止字段泄漏检查
  - `test_deterministic` — 确定性检查
  - `test_raw_output_with_sql_block` — Raw output 提取

---

## 9. py_compile 结果

```
$ python -m py_compile steps.py preview_step_sequences.py
```

**所有文件编译通过，无语法错误。**

---

## 10. 边界检查结果

### 10.1 禁止符号扫描
在 `steps.py` 中搜索下游字段：
```
A_i_t, H_i_t, I_plus, I_minus, rho, x_dir, x_res, s_i_t, Q_i_t_h, 
tau_i, final_label, endpoint_accuracy, execution_accuracy, 
train, fit, predict, calibration, threshold, plot, matplotlib, seaborn
```

**结果**: 仅出现在 `_FORBIDDEN_META_FIELDS` 黑名单中（第 55-57 行），功能代码中无引用。✅ 通过

### 10.2 Step 边界
- ✅ t 从 1 开始，严格递增
- ✅ step_id 格式正确：`{sample_id}::cp::{t:04d}`
- ✅ 不使用 gold SQL
- ✅ 不执行 SQL
- ✅ 不读取 final execution result
- ✅ 不引入下游字段

---

## 11. 后续 Prompt 5 的建议输入文件

| 文件 | 路径 | 用途 |
|------|------|------|
| Preview JSONL | `artifacts/observation_debug/step_sequence_preview.jsonl` | 验证 verification 规则引擎输入格式 |
| Preview Report | `artifacts/observation_debug/step_sequence_preview_report.json` | 了解 step 类型分布和来源 |
| Steps.py | `src/mhiedew/observation/steps.py` | 提供 Step dataclass 定义 |
| Protocol | `FROZEN_PROTOCOL_MANIFEST.json` | 提供 protocol_hash 和配置 |

---

## 12. 验收标准检查

| # | 验收标准 | 状态 |
|---|---------|------|
| 1 | `build_step_sequence` 不再 raise NotImplementedError | ✅ 通过 |
| 2 | `assign_step_ids` 原有行为不被破坏 | ✅ 通过 |
| 3 | 第 3 步已有 16 个测试继续通过 | ✅ 通过 (22/22) |
| 4 | 新增 step extraction 测试通过 | ✅ 通过 (6/6) |
| 5 | py_compile 通过 | ✅ 通过 |
| 6 | 不修改旧项目文件 | ✅ 通过 |
| 7 | 不调用 LLM | ✅ 通过 |
| 8 | 不使用 gold SQL 构造 step | ✅ 通过 |
| 9 | 不引入 §3.3/§3.4 下游字段 | ✅ 通过 |
| 10 | 能生成 preview JSONL 和 report | ✅ 通过 |
| 11 | 生成 migration 文档和执行报告 | ✅ 通过 |
| 12 | 真实 DATA_SRC 成功处理 (5/5) | ✅ 通过 |

---

**报告完成时间**: 2026-06-03  
**执行状态**: ✅ 第 4 步完成  
**下一步**: Prompt 5 — 迁移 verification rule engine
