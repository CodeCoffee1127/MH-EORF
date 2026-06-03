# DEPENDENCY_MIGRATION_REPORT.md

> **生成时间**: 2026-06-03  
> **步骤**: 第 6 步 — 增量迁移 dependency extraction  
> **状态**: ✅ 完成

---

## 1. 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/slrdaf/observation/dependencies.py` | 增量更新 | 实现依赖提取规则及 public API |
| `experiments/preview_dependency_sets.py` | 新建 | Dependency preview 脚本 |
| `tests/test_dependency_extraction.py` | 新建 | 10 个测试用例 |
| `docs/migration_dependency_sets.md` | 新建 | 迁移文档 |
| `DEPENDENCY_MIGRATION_REPORT.md` | 新建 | 本文件 |

---

## 2. 旧项目来源文件清单

| 文件 | 路径 | 用途 |
|------|------|------|
| `dependency_extractor.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/cpfc/` | SQL 依赖图提取 |
| `sql_cpfc.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/cpfc/` | CPFC 协议实例化 |
| `schema.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/step_extractor/` | 数据结构定义 |
| `segmentation.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/step_extractor/` | 结构解析 |
| `bridge_sql_pipeline.py` | `Material/ExternalFalsifiableMeasurementforSubmission/code/step_extractor/` | SQL 桥接 |

---

## 3. 迁移函数清单

| 函数 | 类型 | 说明 |
|------|------|------|
| `extract_dependency_set()` | 公开 | 提取单个 checkpoint 的依赖集合 |
| `extract_all_dependency_sets()` | 公开 | 提取序列中所有 checkpoint 的依赖集合 |
| `validate_historical_dependencies()` | 公开 | 验证历史依赖边界 |
| `_infer_sql_clause_order_deps()` | 内部 | SQL clause order 依赖推断 |
| `_infer_identifier_overlap_deps()` | 内部 | Identifier overlap 依赖推断 |
| `_infer_explicit_parent_deps()` | 内部 | Explicit parent 依赖推断 |
| `_infer_verification_evidence()` | 内部 | Verification 证据提取 |
| `_build_checkpoint_lookup()` | 内部 | 构建 checkpoint 查找表 |
| `_previous_checkpoints()` | 内部 | 获取历史 checkpoint |
| `_extract_checkpoint_text()` | 内部 | 提取 checkpoint 文本 |
| `_extract_checkpoint_clause()` | 内部 | 提取 SQL clause |
| `_extract_identifiers()` | 内部 | 提取 identifier |
| `_deduplicate_edges()` | 内部 | 去重边 |
| `_load_verification_results()` | 内部 | 加载 verification results |

---

## 4. 依赖规则清单

| 规则 | dependency_type | 说明 |
|------|----------------|------|
| SQL clause order | `sql_clause_order:schema_to_column` | SELECT 依赖 FROM/JOIN |
| SQL clause order | `sql_clause_order:schema_to_predicate` | WHERE/HAVING 依赖 FROM/JOIN |
| SQL clause order | `sql_clause_order:column_to_aggregation` | GROUP BY/ORDER BY 依赖 SELECT |
| SQL clause order | `sql_clause_order:schema_to_aggregation` | GROUP BY/ORDER BY 依赖 FROM/JOIN |
| SQL clause order | `sql_clause_order:schema_chain` | JOIN 依赖前一个 FROM/JOIN |
| Identifier overlap | `identifier_overlap` | 共享非 SQL 关键字 identifier |
| Explicit parent | `explicit_parent` | 从 metadata/content 提取 parent |

---

## 5. Dependency_type 分布

```
sql_clause_order:schema_chain: 4
identifier_overlap: 3
sql_clause_order:schema_to_predicate: 4
sql_clause_order:schema_to_aggregation: 2
```

---

## 6. E_minus 边界检查结果

- ✅ 所有 E_minus 只包含历史 checkpoint (predecessor_t < current_t)
- ✅ 不包含当前 checkpoint
- ✅ 不包含未来 checkpoint
- ✅ 不包含不存在 checkpoint
- ✅ 如果无法确定依赖，E_minus=[]
- ✅ `validate_historical_dependencies()` 验证通过

---

## 7. Verification Evidence 使用方式

- verification results 仅作为证据记录在 `metadata["verification_context"]` 中
- syntax passed=True → 当前 checkpoint 可作为结构节点参与依赖
- type/execution unverifiable=True → 记录 "verification_context_unavailable"
- **不得**根据 passed/unverifiable 计算权重
- **不得**生成 I_plus/I_minus/rho
- **unverifiable 不是 failed dependency**

---

## 8. Preview 结果

```
Samples attempted: 5
Samples succeeded: 5
Samples skipped: 0
Total dependency sets: 21
Total edges: 13
Empty dependency sets: 10
Max E_minus size: 2
Future dependency violations: 0
Missing predecessor violations: 0
Verification evidence used: 5 samples
Unverifiable not treated as failure: true

Dependency type distribution:
  sql_clause_order:schema_chain: 4
  identifier_overlap: 3
  sql_clause_order:schema_to_predicate: 4
  sql_clause_order:schema_to_aggregation: 2
```

---

## 9. 测试结果

```
$ pytest tests -q
..........................................                               [100%]
42 passed in 0.11s
```

**测试覆盖**:
- ✅ 第 3 步原有 16 个测试全部通过
- ✅ 第 4 步新增 6 个 checkpoint extraction 测试全部通过
- ✅ 第 5 步新增 10 个 verification rules 测试全部通过
- ✅ 第 6 步新增 10 个 dependency extraction 测试全部通过

---

## 10. py_compile 结果

```
$ python -m py_compile dependencies.py preview_dependency_sets.py
```

**所有文件编译通过，无语法错误。**

---

## 11. 禁止符号扫描结果

在 `dependencies.py` 中搜索下游字段：
```
A_i_t, H_i_t, I_plus, I_minus, Inec, rho, risk_memory, dependency_weight, 
c_i_j_to_t, x_dir, x_res, s_i_t, Q_i_t_h, tau_i, final_label, 
endpoint_accuracy, execution_accuracy, train, fit, predict, 
calibration, threshold, plot, matplotlib, seaborn, Beta, entropy
```

**结果**: 无匹配。✅ 通过

---

## 12. 是否修改旧项目文件

**否**。本步骤仅读取旧项目文件作为参考，未修改任何旧项目文件。

---

## 13. 后续 Prompt 7 的建议输入文件

| 文件 | 路径 | 用途 |
|------|------|------|
| Checkpoint Preview | `artifacts/observation_debug/checkpoint_sequence_preview.jsonl` | 提供 checkpoint 序列 |
| Verification Preview | `artifacts/observation_debug/verification_preview.jsonl` | 提供验证结果 |
| Dependency Preview | `artifacts/observation_debug/dependency_sets_preview.jsonl` | 提供 E_minus 约束，Prompt 7 只能扰动 E_minus 中的历史 predecessor |
| Dependency Report | `artifacts/observation_debug/dependency_sets_preview_report.json` | 了解依赖分布 |
| Dependencies.py | `src/slrdaf/observation/dependencies.py` | 提供 DependencySet dataclass 定义 |
| Protocol | `FROZEN_PROTOCOL_MANIFEST.json` | 提供 protocol_hash 和配置 |

---

## 14. 验收标准检查

| # | 验收标准 | 状态 |
|---|---------|------|
| 1 | `extract_dependency_set` 不再 raise NotImplementedError | ✅ 通过 |
| 2 | `extract_all_dependency_sets` 不再 raise NotImplementedError | ✅ 通过 |
| 3 | `validate_historical_dependencies` 原有测试继续通过 | ✅ 通过 |
| 4 | 每个 checkpoint 都能输出一个 DependencySet | ✅ 通过 |
| 5 | E_minus 只包含历史 checkpoint | ✅ 通过 |
| 6 | dependency_edges 中 predecessor_t < successor_t | ✅ 通过 |
| 7 | future parent 被过滤或报错，不得进入输出 | ✅ 通过 |
| 8 | verification evidence 只作为 evidence，不作为风险或分数 | ✅ 通过 |
| 9 | unverifiable=True 不被解释为 failed dependency | ✅ 通过 |
| 10 | 不计算 I_plus、I_minus、Inec、rho、risk_memory、dependency_weight | ✅ 通过 |
| 11 | 不使用 tau_i、final_label、endpoint_accuracy、y_i_t_h | ✅ 通过 |
| 12 | 第 3/4/5 步已有测试继续通过 | ✅ 通过 (42/42) |
| 13 | 新增 dependency tests 通过 | ✅ 通过 (10/10) |
| 14 | py_compile 通过 | ✅ 通过 |
| 15 | 不修改旧项目文件 | ✅ 通过 |
| 16 | 不调用 LLM | ✅ 通过 |
| 17 | 能生成 dependency preview JSONL 和 report | ✅ 通过 |
| 18 | 生成 migration 文档和执行报告 | ✅ 通过 |
| 19 | pytest 通过 | ✅ 通过 (42/42) |

---

**报告完成时间**: 2026-06-03  
**执行状态**: ✅ 第 6 步完成  
**下一步**: Prompt 7 — 迁移 perturbation response generation
