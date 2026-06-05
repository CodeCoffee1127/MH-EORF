# Migration: Dependency Sets

> **创建时间**: 2026-06-03
> **步骤**: 第 6 步 — 增量迁移 dependency extraction
> **状态**: ✅ 完成

---

## 1. 本步骤迁移目标

实现 `D:\SL-RDAF\src\slrdaf\observation\dependencies.py` 中的：
- `extract_dependency_set()` — 提取单个 step 的历史依赖集合 E_minus
- `extract_all_dependency_sets()` — 提取序列中所有 step 的依赖集合

本步骤只生成 DependencySet、DependencyEdge、E_minus、dependency_edges，不生成 §3.3 依赖风险特征。

---

## 2. 旧项目来源文件

| 旧项目文件 | 用途 | 迁移状态 |
|-----------|------|---------|
| `code/cpfc/dependency_extractor.py` | SQL 依赖图提取 | ✅ 已阅读，提取启发式规则 |
| `code/cpfc/sql_cpfc.py` | CPFC 协议实例化 | ✅ 已参考 |
| `code/step_extractor/schema.py` | 数据结构定义 | ✅ 已参考 |
| `code/step_extractor/segmentation.py` | 结构解析 | ✅ 已参考 |
| `code/step_extractor/bridge_sql_pipeline.py` | SQL 桥接 | ✅ 已参考 |

---

## 3. 新项目目标文件

| 新文件 | 状态 |
|--------|------|
| `src/slrdaf/observation/dependencies.py` | ✅ 已增量更新 |
| `experiments/preview_dependency_sets.py` | ✅ 已创建 |
| `tests/test_dependency_extraction.py` | ✅ 已创建 (10 个测试) |
| `artifacts/observation_debug/dependency_sets_preview.jsonl` | ✅ 已生成 |
| `artifacts/observation_debug/dependency_sets_preview_report.json` | ✅ 已生成 |
| `docs/migration_dependency_sets.md` | ✅ 已创建 |

---

## 4. E_minus 定义

E_minus_{i,t} 是 step p_{i,t} 的历史结构依赖集合，包含所有 t' < t 的 step_id。

**规则**：
- 只包含历史 step
- 不包含当前 step
- 不包含未来 step
- 不包含不存在 step
- 如果无法确定依赖，E_minus=[]

---

## 5. DependencyEdges 结构

每条边包含：
- `predecessor_id`: 前驱 step_id
- `successor_id`: 后继 step_id
- `dependency_type`: 依赖类型
- `evidence`: 证据字典

**evidence 结构示例**：
```json
{
  "rule": "identifier_overlap",
  "current_step_type": "predicate_binding",
  "predecessor_step_type": "column_reference",
  "current_t": 3,
  "predecessor_t": 1,
  "shared_identifiers": ["temperature", "device_id"]
}
```

---

## 6. 四类依赖证据

### A. SQL Clause Order Dependencies
基于 step_type 推断结构依赖：
- `column_reference` → 依赖最近的 `schema_linking`
- `predicate_binding` → 依赖 `schema_linking`
- `aggregation_or_ordering` → 依赖 `column_reference` 或 `schema_linking`
- `schema_linking` → 依赖前一个 `schema_linking` (chain)

### B. Identifier Overlap Dependencies
提取非 SQL 关键字 identifier，检查当前 step 与历史 step 的共享标识符。
- 忽略 SQL keywords (SELECT, FROM, WHERE, JOIN 等)
- dependency_type = "identifier_overlap"
- evidence 记录 shared_identifiers

### C. Explicit Parent Evidence
从 step.metadata 或 step.content 中提取 parent 信息：
- parent_ids, parents, predecessors, dependencies 等字段
- 只保留存在于 sequence 且 t 更小的 parent
- 过滤 future parent 和 missing parent

### D. Verification Rule-Trigger Evidence
使用 context 中的 verification_results 作为证据：
- syntax passed=True → 当前 step 可作为结构节点参与依赖
- type/execution unverifiable=True → 记录 "verification_context_unavailable"
- **不得**根据 passed/unverifiable 计算权重
- **不得**生成 I_plus/I_minus/rho

---

## 7. Verification Evidence 的边界

1. **syntax pass** 可支持结构节点参与依赖提取
2. **type/execution unverifiable** 只能记录上下文不足
3. **unverifiable 不是 failed dependency**
4. verification evidence 只作为 evidence 记录在 metadata 中，不创建边，不计算风险

---

## 8. 删除或未迁移逻辑

| 逻辑 | 原因 |
|------|------|
| Parent ablation | 属于 §3.3，禁止迁移 |
| I_plus / I_minus | 属于 §3.3 诊断特征，禁止迁移 |
| Inec | 属于 §3.3，禁止迁移 |
| rho / risk memory | 属于 §3.3，禁止迁移 |
| Dependency weights | 属于 §3.3，禁止迁移 |
| Analysis features (A_i_t, H_i_t, x_dir, x_res) | 属于 §3.3，禁止迁移 |
| Training/calibration/visualization | 属于 §3.4/§4.x，禁止迁移 |
| sqlglot 依赖 | 新项目使用标准库 re，不引入新依赖 |
| compute_dependency_strength() | 计算 I_plus/I_minus，禁止迁移 |

---

## 9. Preview 结果摘要

```
Samples succeeded: 5/5
Total dep sets: 21
Total edges: 13
Empty dep sets: 10
Max E_minus size: 2

Dependency type distribution:
  sql_clause_order:schema_chain: 4
  identifier_overlap: 3
  sql_clause_order:schema_to_predicate: 4
  sql_clause_order:schema_to_aggregation: 2

Verification evidence used: 5 samples
Unverifiable not treated as failure: true
```

**说明**:
- 10 个 empty dep sets 是因为 t=1 的 step 没有历史依赖
- 依赖类型分布符合 SQL clause order 和 identifier overlap 规则
- verification evidence 仅记录在 metadata 中，未创建风险特征

---

## 10. 与 Prompt 7 的接口

### 10.1 Dependency Sets 作为 Perturbation Predecessor 约束

- `dependency_sets_preview.jsonl` 将作为 perturbation response 的 predecessor 约束
- Prompt 7 只能扰动 E_minus 中的历史 predecessor
- 不得扰动未来 step 或不存在 step

### 10.2 禁止

- Prompt 7 **不得**使用 dependency sets 计算 I_plus/I_minus
- Prompt 7 **不得**使用 dependency sets 生成 §3.3 特征
- 只能使用 E_minus 作为扰动目标约束

---

**文档完成时间**: 2026-06-03  
**状态**: ✅ 迁移完成
