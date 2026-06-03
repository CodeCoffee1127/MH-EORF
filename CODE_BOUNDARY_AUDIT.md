# CODE_BOUNDARY_AUDIT.md

> **生成时间**: 2026-06-03  
> **步骤**: 第 9A 步 — 仓库边界清理与代码审计  
> **状态**: ✅ 完成

---

## 1. 扫描目录

- `D:\SL-RDAF\src\slrdaf\observation`
- `D:\SL-RDAF\experiments`
- `D:\SL-RDAF\tests`
- `D:\SL-RDAF\schemas`

---

## 2. 禁止符号命中表

### 2.1 `src/slrdaf/observation/`

| 文件 | 行号 | 符号 | 类型 | 说明 |
|------|------|------|------|------|
| `dependencies.py` | 290 | `risk`, `score` | 文档字符串 | `"""Extract verification context for evidence. Does NOT create risk/score."""` |
| `leakage.py` | 5 | `training`, `calibration`, `evaluation` | 文档字符串 | `from downstream tasks (training, calibration, evaluation).` |
| `leakage.py` | 18-46 | `tau_i`, `final_label`, `endpoint_accuracy`, `execution_accuracy`, `A_i_t`, `H_i_t`, `I_plus`, `I_minus`, `Inec`, `rho`, `x_dir`, `x_res`, `s_i_t`, `hazard`, `loss`, `logit` | 黑名单常量 | `FORBIDDEN_FIELD_NAMES` 集合定义，用于防泄漏检查 |
| `checkpoints.py` | 55-57 | `final_label`, `endpoint_accuracy`, `execution_accuracy`, `tau`, `tau_i`, `y_i_t_h`, `A_i_t`, `H_i_t`, `I_plus`, `I_minus`, `rho`, `x_dir`, `x_res` | 黑名单常量 | `_FORBIDDEN_META_FIELDS` 集合定义，用于过滤 metadata |

### 2.2 `experiments/`

无命中。

### 2.3 `tests/`

| 文件 | 行号 | 符号 | 类型 | 说明 |
|------|------|------|------|------|
| 多个测试文件 | 多处 | `final_label`, `tau_i`, `x_dir`, `A_i_t`, `H_i_t`, `I_plus`, `I_minus`, `rho`, `risk_memory`, `dependency_weight`, `score`, `feature` | 测试断言/黑名单 | 测试代码中用于验证 forbidden fields 不被输出 |

### 2.4 `schemas/`

| 文件 | 行号 | 符号 | 类型 | 说明 |
|------|------|------|------|------|
| `observation_plane.schema.json` | 69 | `tau_i` | 描述字符串 | `"description": "Whether tau_i was used"` |
| `observation_plane.schema.json` | 81 | `A_i_t`, `H_i_t` | 描述字符串 | `"description": "Whether downstream features (A_i_t, H_i_t, etc.) were used"` |
| `perturbation_response.schema.json` | 75 | `I_plus`, `I_minus` | 描述字符串 | `"description": "Summary of perturbation response (no I_plus/I_minus)"` |

---

## 3. 功能代码是否包含下游逻辑

**结论**: ❌ 否。

所有命中的禁止符号均出现在以下位置：
- `leakage.py` 和 `checkpoints.py` 中的 **黑名单常量定义**（用于防泄漏检查）
- `dependencies.py` 中的 **文档字符串**（说明不创建 risk/score）
- `tests/` 中的 **测试断言**（验证输出不包含 forbidden fields）
- `schemas/` 中的 **描述字符串**（说明 schema 字段用途）

**没有任何功能代码实现下游逻辑（训练、校准、评估、可视化、特征工程）。**

---

## 4. 黑名单/测试/文档中允许出现的说明

| 位置 | 允许原因 |
|------|---------|
| `leakage.py` 黑名单 | 必须包含下游字段名称以进行防泄漏扫描 |
| `checkpoints.py` 黑名单 | 必须包含下游字段名称以过滤 metadata |
| `dependencies.py` 文档字符串 | 说明本函数不创建 risk/score，属于合规声明 |
| `tests/` 测试断言 | 必须包含下游字段名称以验证输出合规 |
| `schemas/` 描述字符串 | 说明 leakage_check 字段的用途，属于 schema 文档 |

---

## 5. 是否发现训练、校准、评估、可视化混入 §3.2

**结论**: ❌ 未发现。

- `src/slrdaf/observation/` 仅包含 §3.2 核心逻辑（checkpoint、verification、dependency、perturbation、observation_plane、protocol、io、leakage）
- `experiments/` 仅包含构建和验证脚本
- `tests/` 仅包含单元测试
- `schemas/` 仅包含数据 schema 定义
- 无任何训练、校准、评估、可视化代码混入

---

## 6. 结论

✅ **代码边界清晰，无下游逻辑混入。**  
所有禁止符号均出现在黑名单、测试或文档中，功能代码严格遵守 §3.2 边界。

---

**审计完成时间**: 2026-06-03  
**状态**: ✅ 通过
