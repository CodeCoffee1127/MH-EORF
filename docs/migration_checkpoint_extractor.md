# Migration: Checkpoint Extractor

> **创建时间**: 2026-06-03  
> **步骤**: 第 4 步 — 增量迁移 checkpoint sequence construction  
> **状态**: ✅ 完成

---

## 1. 本步骤迁移目标

实现 `D:\SL-RDAF\src\slrdaf\observation\checkpoints.py` 中的 `build_checkpoint_sequence()` 函数，将原始推理链 / agent output / generated SQL construction trace 转换为 `CheckpointSequence`。

---

## 2. 旧项目来源文件

| 旧项目文件 | 用途 | 迁移状态 |
|-----------|------|---------|
| `code/step_extractor/step_extractor.py` | VerifierDrivenStepExtractor 核心逻辑 | ✅ 已阅读，提取 trace step 处理逻辑 |
| `code/step_extractor/segmentation.py` | StructureParse 结构解析 | ✅ 已阅读，提取 SQL 子句边界判定规则 |
| `code/step_extractor/schema.py` | StepObject、ParseStatus 定义 | ✅ 已阅读，映射到 Checkpoint dataclass |
| `code/step_extractor/bridge_sql_pipeline.py` | clause_records → StepObject 桥接 | ✅ 已阅读，提取 SQL 分段逻辑 |
| `code/step_extractor/paper_based_step_extractor_reconstruction.py` | 重构助手与 normalize_reasoning_step | ✅ 已阅读，提取字段映射规则 |
| `code/cpfc/sql_cpfc.py` | CPFC SQL 处理 | ✅ 已阅读，参考 SQL 解析策略 |

---

## 3. 新项目目标文件

| 新文件 | 状态 |
|--------|------|
| `src/slrdaf/observation/checkpoints.py` | ✅ 已增量更新 |
| `experiments/preview_checkpoint_sequences.py` | ✅ 已创建 |
| `tests/test_checkpoint_extraction.py` | ✅ 已创建 |
| `artifacts/observation_debug/checkpoint_sequence_preview.jsonl` | ✅ 已生成 |
| `artifacts/observation_debug/checkpoint_sequence_preview_report.json` | ✅ 已生成 |

---

## 4. 迁移保留的逻辑

### 4.1 Trace Step Extraction
- 从 `steps`, `intermediate_steps`, `raw_trace` 等字段提取结构化步骤
- 每个 step dict 转成一个 Checkpoint
- 保留 `legacy_type` 和 `legacy_step_index` 在 metadata 中

### 4.2 SQL Clause Segmentation
- 轻量级正则表达式分段（不依赖 sqlparse 等新依赖）
- 匹配 SQL 关键字：SELECT, FROM, JOIN, WHERE, GROUP BY, ORDER BY, HAVING, LIMIT
- 每个子句转成一个 Checkpoint

### 4.3 Checkpoint Type Mapping
| SQL 子句 / 内容特征 | checkpoint_type |
|-------------------|----------------|
| SELECT 列引用 | `column_reference` |
| WHERE / HAVING 谓词 | `predicate_binding` |
| FROM / JOIN 表引用 | `schema_linking` |
| GROUP BY / ORDER BY / LIMIT / 聚合函数 | `aggregation_or_ordering` |
| 无法识别 | `other` |

### 4.4 Checkpoint ID Assignment
- 格式：`{sample_id}::cp::{t:04d}`
- t 从 1 开始，严格递增
- 使用已测试的 `assign_checkpoint_ids()` 函数

---

## 5. 删除或未迁移的逻辑

| 逻辑 | 原因 |
|------|------|
| Verifier 门控 | 属于 §3.2 验证规则引擎，将在 Prompt 5 迁移 |
| Dependency Extraction | 属于 §3.2 依赖提取，将在 Prompt 6 迁移 |
| Perturbation | 属于 §3.2 扰动响应，将在 Prompt 7 迁移 |
| A_i_t / H_i_t Feature Construction | 属于 §3.3 诊断特征工程，禁止迁移 |
| Model Training | 属于 §3.4，禁止迁移 |
| Calibration | 属于 §3.5，禁止迁移 |
| Visualization | 属于 §4.x，禁止迁移 |
| VerifierDrivenStepExtractor 字符级 buffer 逻辑 | 新项目使用数据源已结构化的 trace/SQL，不需要字符级解析 |

---

## 6. Checkpoint Boundary 判定规则

1. **Structured Trace**: 每个 step dict 是一个 checkpoint 边界
2. **SQL Text**: 每个 SQL 子句（SELECT/FROM/WHERE/JOIN/GROUP BY/ORDER BY/HAVING/LIMIT）是一个 checkpoint 边界
3. **Raw Output**: 
   - 优先提取 ```sql 代码块中的 SQL 子句
   - 若无代码块，解析 `Step N:` 标记作为边界
4. **Gold SQL**: 禁止使用，若仅存在 gold SQL 则报错跳过

---

## 7. Generated SQL Fallback 规则

当样本中不存在结构化 trace 时：
1. 尝试从 `generated_sql`, `pred_sql`, `prediction_sql`, `predicted_sql`, `output_sql`, `sql_prediction` 字段提取
2. 使用正则表达式分段
3. 不执行 SQL，不判断正确性，不读取执行结果
4. 不引入新依赖（仅使用 `re` 标准库）

---

## 8. Gold SQL 禁用规则

- **禁止字段**: `gold_sql`, `gold_query`, `ground_truth_sql`, `label_sql`
- **处理方式**: 若样本中仅存在 gold SQL 而不存在 generated trace/sql，则 raise ValueError 并跳过
- **原因**: Gold SQL 不是模型生成过程，不能反映推理链退化

---

## 9. DATA_SRC Preview 结果摘要

```
Input: D:\SL-RDAF\data\data
Samples attempted: 5
Samples succeeded: 5
Samples skipped: 0

Checkpoint type distribution:
  - schema_linking: 9
  - column_reference: 5
  - predicate_binding: 4
  - aggregation_or_ordering: 2
  - other: 1

Source field distribution:
  - pred_sql: 21
```

**说明**: 数据源 `model_outputs.jsonl` 包含 `pred_sql` 字段（模型预测 SQL），成功提取为 checkpoint sequence。

---

## 10. 未解决问题

1. **复杂 SQL 嵌套**: 当前正则分段对子查询、CTE 等复杂结构支持有限，将在后续优化
2. **多语句 SQL**: 当前假设单条 SQL，多语句场景需额外处理
3. **Trace 格式多样性**: 不同 LLM 输出的 trace 格式可能不同，需持续适配

---

**文档完成时间**: 2026-06-03  
**状态**: ✅ 迁移完成
