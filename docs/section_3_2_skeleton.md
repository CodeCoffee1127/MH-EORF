# Section 3.2 Observation Plane Construction - Skeleton

> **创建时间**: 2026-06-03  
> **步骤**: 第 3 步 — 创建 §3.2 观测平面生成代码骨架与数据 schema  
> **状态**: 骨架就绪，等待 Prompt 4-8 迁移实现

---

## 1. 目录结构

```
D:\SL-RDAF\
├── src\slrdaf\observation\          # §3.2 核心模块（独立于下游模块）
│   ├── __init__.py                  # 包入口
│   ├── protocol.py                  # 协议配置加载
│   ├── checkpoints.py               # 检查点序列构造
│   ├── verification.py              # 验证规则引擎
│   ├── dependencies.py              # 历史结构依赖集合提取
│   ├── perturbations.py             # 扰动响应记录生成
│   ├── observation_plane.py         # 观测平面组装
│   ├── io.py                        # JSON/JSONL IO 工具
│   └── leakage.py                   # 防泄漏检查
├── schemas\                         # JSON Schema 定义
│   ├── checkpoint.schema.json
│   ├── verification_result.schema.json
│   ├── dependency_set.schema.json
│   ├── perturbation_response.schema.json
│   ├── observation_plane.schema.json
│   └── observation_protocol.schema.json
├── experiments\                     # CLI 脚本骨架
│   ├── build_observation_plane.py
│   ├── validate_observation_plane.py
│   └── inspect_observation_protocol.py
├── tests\                           # 单元测试
│   ├── test_protocol_loading.py
│   ├── test_checkpoint_ids.py
│   ├── test_dependency_boundary.py
│   ├── test_perturbation_hash.py
│   ├── test_leakage_guard.py
│   ├── test_schema_files.py
│   └── test_observation_plane_assembly.py
├── artifacts\                       # 输出目录
│   ├── observation_debug\
│   └── observation_plane\
└── docs\                            # 文档
    └── section_3_2_skeleton.md      # 本文件
```

---

## 2. 各模块职责

### 2.1 protocol.py
- **职责**: 加载并验证 FROZEN_PROTOCOL_MANIFEST.json
- **核心函数**: `load_protocol(manifest_path) -> ObservationProtocol`
- **验证项**:
  - temperature 必须为 0
  - random_seed 必须存在
  - protocol_hash 必须为 64 字符
  - llm_version、rule_library_version、perturbation_family_version、N、M 未确认时保持 None

### 2.2 checkpoints.py
- **职责**: 检查点序列构造
- **核心数据类**: `Checkpoint`, `CheckpointSequence`
- **已实现**: `assign_checkpoint_ids()` — 分配 checkpoint ID
- **待迁移**: `build_checkpoint_sequence()` — Prompt 4

### 2.3 verification.py
- **职责**: 验证规则引擎
- **核心数据类**: `VerificationRule`, `VerificationResult`, `RuleLibrary`
- **已实现**: `load_rule_library()` — 加载空规则库
- **待迁移**: `verify_checkpoint()`, `verify_checkpoint_sequence()` — Prompt 5

### 2.4 dependencies.py
- **职责**: 历史结构依赖集合提取
- **核心数据类**: `DependencyEdge`, `DependencySet`
- **已实现**: `validate_historical_dependencies()` — 验证依赖边界
- **待迁移**: `extract_dependency_set()`, `extract_all_dependency_sets()` — Prompt 6

### 2.5 perturbations.py
- **职责**: 扰动响应记录生成
- **核心数据类**: `PerturbationFamily`, `PerturbationResponse`
- **已实现**: `hash_perturbation_payload()` — 扰动 payload 哈希
- **待迁移**: `perturb_checkpoint()`, `generate_perturbation_responses()` — Prompt 7

### 2.6 observation_plane.py
- **职责**: 观测平面组装
- **核心数据类**: `ObservationRecord`, `ObservationPlane`
- **已实现**: `assemble_observation_plane()` — 基础组装逻辑
- **待迁移**: `build_observation_plane()` — Prompt 8

### 2.7 io.py
- **职责**: JSON/JSONL 读写工具
- **核心函数**: `write_jsonl()`, `read_jsonl()`, `write_json()`, `read_json()`, `sha256_file()`

### 2.8 leakage.py
- **职责**: 防泄漏检查
- **核心函数**: `scan_forbidden_fields()`, `assert_no_forbidden_fields()`
- **黑名单**: `FORBIDDEN_FIELD_NAMES` — 包含下游字段名称

---

## 3. Schema 列表

| Schema 文件 | 描述 | 核心字段 |
|------------|------|---------|
| `checkpoint.schema.json` | 检查点定义 | sample_id, checkpoint_id, t, checkpoint_type, content |
| `verification_result.schema.json` | 验证结果 | sample_id, checkpoint_id, rule_id, rule_type, passed, unverifiable |
| `dependency_set.schema.json` | 依赖集合 | sample_id, checkpoint_id, E_minus, dependency_edges |
| `perturbation_response.schema.json` | 扰动响应 | sample_id, checkpoint_id, perturbation_payload_hash, response_summary |
| `observation_plane.schema.json` | 观测平面 | sample_id, observation_plane[], leakage_check |
| `observation_protocol.schema.json` | 协议配置 | manifest_name, protocol_hash, determinism, scope |

---

## 4. 与论文 §3.2 符号对应关系

| 论文符号 | 代码模块 | 数据类/函数 |
|---------|---------|------------|
| p_{i,t} | checkpoints.py | `Checkpoint` |
| P_i (检查点序列) | checkpoints.py | `CheckpointSequence` |
| v_{i,t} | verification.py | `VerificationResult` |
| E_minus_{i,t} | dependencies.py | `DependencySet.E_minus` |
| R_{i,t} | perturbations.py | `PerturbationResponse` |
| O_i | observation_plane.py | `ObservationPlane` |

---

## 5. 与旧项目文件的后续迁移映射

> **注意**: 本步骤未迁移旧代码，仅建立映射关系。

| 旧项目文件 | 新模块 | 迁移时机 |
|-----------|-------|---------|
| `code/step_extractor/step_extractor.py` | `checkpoints.py` | Prompt 4 |
| `code/step_extractor/segmentation.py` | `checkpoints.py` | Prompt 4 |
| `code/step_extractor/schema.py` | `checkpoints.py` | Prompt 4 |
| `code/verifier/vsp_verifier.py` | `verification.py` | Prompt 5 |
| `code/verifier/constraint_rules.py` | `verification.py` | Prompt 5 |
| `code/cpfc/dependency_extractor.py` | `dependencies.py` | Prompt 6 |
| `code/generation/candidate_generator.py` | `perturbations.py` | Prompt 7 |

---

## 6. 禁止字段清单

以下字段**禁止**出现在 §3.2 观测平面中（属于 §3.3/§3.4）：

- `A_i_t`, `H_i_t`, `I_plus`, `I_minus`, `Inec`, `rho` — 诊断特征工程
- `x_dir`, `x_res` — 模型输入
- `s_i_t`, `delta_s_i_t` — 递推状态
- `Q`, `q`, `calibrated_risk`, `prediction` — 风险预测
- `tau`, `tau_i`, `first_degradation` — 退化时间
- `final_label`, `endpoint_accuracy`, `execution_accuracy` — 端点标签
- `y_i_t_h`, `y_h1`, `y_h2`, `y_h3` — 多视野标签
- `hazard`, `loss`, `logit` — 训练相关

---

## 7. 后续 Prompt 迁移入口

| Prompt | 迁移模块 | 实现函数 |
|--------|---------|---------|
| **Prompt 4** | `checkpoints.py` | `build_checkpoint_sequence()` |
| **Prompt 5** | `verification.py` | `verify_checkpoint()`, `verify_checkpoint_sequence()` |
| **Prompt 6** | `dependencies.py` | `extract_dependency_set()`, `extract_all_dependency_sets()` |
| **Prompt 7** | `perturbations.py` | `perturb_checkpoint()`, `generate_perturbation_responses()` |
| **Prompt 8** | `observation_plane.py` + `experiments/` | `build_observation_plane()`, 完整 CLI |

---

## 8. 与旧 sl_rdaf\ 包的关系

- **旧包**: `D:\SL-RDAF\sl_rdaf\` — 包含 training、calibration、evaluation 等下游模块
- **新包**: `D:\SL-RDAF\src\slrdaf\observation\` — 独立的 §3.2 观测平面构造模块
- **隔离原则**: 新包不依赖旧包的 training、calibration、evaluation 模块
- **数据流向**: 新包生成 observation planes → 旧包读取 observation planes 作为输入

---

**文档完成时间**: 2026-06-03  
**状态**: ✅ 骨架就绪
