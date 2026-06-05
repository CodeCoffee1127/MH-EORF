# Migration: Verification Rules

> **创建时间**: 2026-06-03
> **步骤**: 第 5 步 — 增量迁移 verification rule engine
> **状态**: ✅ 完成

---

## 1. 本步骤迁移目标

实现 `D:\SL-RDAF\src\slrdaf\observation\verification.py` 中的：
- `load_rule_library()` — 加载三类核心验证规则
- `verify_checkpoint()` — 对单个 step 应用所有规则
- `verify_checkpoint_sequence()` — 对序列中所有 step 应用规则

本步骤只生成检查点级验证结果 v_{i,t}，不生成 §3.3 analysis 特征。

---

## 2. 旧项目来源文件

| 旧项目文件 | 用途 | 迁移状态 |
|-----------|------|---------|
| `code/verifier/vsp_verifier.py` | VSP 四层验证器核心 | ✅ 已阅读，提取验证逻辑 |
| `code/verifier/constraint_rules.py` | 自动化 SQL 验证规则库 | ✅ 已阅读，提取规则生成逻辑 |
| `code/step_extractor/schema.py` | StepObject 定义 | ✅ 已参考 |
| `configs/experiment_config.yaml` | 实验配置 | ✅ 已参考 |
| `configs/frozen_manifest_v1.0.yaml` | 冻结参数 | ✅ 已参考 |

---

## 3. 新项目目标文件

| 新文件 | 状态 |
|--------|------|
| `src/slrdaf/observation/verification.py` | ✅ 已增量更新 |
| `experiments/preview_verification_results.py` | ✅ 已创建 |
| `tests/test_verification_rules.py` | ✅ 已创建 (10 个测试) |
| `artifacts/observation_debug/verification_preview.jsonl` | ✅ 已生成 |
| `artifacts/observation_debug/verification_preview_report.json` | ✅ 已生成 |
| `docs/migration_verification_rules.md` | ✅ 已创建 |

---

## 4. 规则类型映射

### 4.1 核心规则（三类）

| rule_id | rule_type | trigger | description |
|---------|-----------|---------|-------------|
| `syntax.sql_fragment_parseable` | `syntax` | all | 验证 SQL fragment 或 trace-step 语法非空且可轻量解析 |
| `type.schema_reference_available` | `type` | column_reference,predicate_binding,schema_linking | 验证引用的表/列是否在 schema 中；否则 unverifiable |
| `execution_side_consistency.fragment_context_compatible` | `execution_side_consistency` | sql_clause | 验证局部执行端兼容性；否则 unverifiable |

### 4.2 规则实现细节

**Syntax Constraint**:
- 检查文本非空
- 检查括号平衡
- 检查引号平衡
- 检查 SQL fragment 有意义（非纯空白/注释/markdown fence）
- Clause 特定检查（SELECT 需字段，WHERE 需谓词标记等）

**Type Constraint**:
- 需要 schema context（tables, columns）
- 检查引用列/表是否存在于 schema
- 无 schema 时返回 unverifiable=True

**Execution-side Consistency**:
- 需要数据库路径（db_path, sqlite_path 等）
- 使用 PRAGMA table_info 检查表是否存在
- 只读、安全、局部检查
- 无数据库时返回 unverifiable=True

---

## 5. Unverifiable Policy

### 5.1 语义定义

| passed | unverifiable | 含义 |
|--------|-------------|------|
| True | False | 规则可执行，且通过 |
| False | False | 规则可执行，且明确失败 |
| False | True | 上下文不足，不能验证（**不是** verified failure） |

### 5.2 重要原则

1. **unverifiable ≠ verified failure**
   - unverifiable=True 表示"无法判断"，不是"验证失败"
   - message 必须写明原因，如 "schema context unavailable"

2. **不参与下游计算**
   - 本步骤不实现 A_i_t、H_i_t 等指标
   - 后续 Prompt 6 的 dependency extraction 不得用 unverifiable 结果计算 I_plus/I_minus

3. **安全优先**
   - 无法判断时返回 unverifiable=True，而非强行失败
   - 任何异常必须捕获，写入 message，不得中断整个样本

---

## 6. 删除或未迁移逻辑

| 逻辑 | 原因 |
|------|------|
| Beta smoothing | 属于 §3.3 诊断特征工程，禁止迁移 |
| Verification entropy (H_i_t) | 属于 §3.3，禁止迁移 |
| Analysis feature construction (A_i_t, I_plus, I_minus, rho) | 属于 §3.3，禁止迁移 |
| Calibration | 属于 §3.5，禁止迁移 |
| Threshold selection | 属于 §3.5，禁止迁移 |
| Training | 属于 §3.4，禁止迁移 |
| Visualization | 属于 §4.x，禁止迁移 |
| VSP 四层验证的完整实现 | 仅迁移核心三类规则，简化实现 |
| sqlparse 依赖 | 新项目使用标准库 re，不引入新依赖 |
| joblib 并行 | 本步骤不需要并行，后续可扩展 |

---

## 7. Preview 结果摘要

```
Samples succeeded: 5/5
Total verification results: 63
Passed: 24
Failed: 0
Unverifiable: 39

Rule type distribution:
  syntax: 21
  type: 21
  execution_side_consistency: 21

Unverifiable reasons:
  - schema context unavailable
  - execution context unavailable
```

**说明**: 
- 由于未提供 schema context 和 database context，type 和 execution 规则多数返回 unverifiable=True
- 这是预期行为，符合 unverifiable policy
- syntax 规则全部通过（step 文本有效）

---

## 8. 与 Prompt 6 的接口

### 8.1 Verification Results 作为 Dependency Rule Trigger Evidence

- `verification_results` 可作为 dependency extraction 的规则触发证据
- 例如：syntax passed 的 step 可参与依赖提取
- type unverifiable 的 step 可能需要特殊处理

### 8.2 禁止

- Dependency extraction **不得**计算 I_plus/I_minus
- Dependency extraction **不得**使用 verification results 生成 §3.3 特征
- 只能使用 verification results 作为辅助信息（如过滤无效 step）

---

**文档完成时间**: 2026-06-03  
**状态**: ✅ 迁移完成
