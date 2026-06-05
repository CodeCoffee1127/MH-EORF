# MIGRATION_AUDIT.md

> **生成时间**: 2026-06-03  
> **审计类型**: 只读审计（Read-Only Audit）  
> ** OLD_ROOT**: `D:\SL-RDAF\Material\ExternalFalsifiableMeasurementforSubmission`  
> ** NEW_ROOT**: `D:\SL-RDAF`  
> ** DATA_SRC**: `D:\SL-RDAF\data\data`  
> ** 审计目标**: 识别 §3.2 "Step-level Observable Representation" 可迁移模块，冻结协议参数，区分禁止迁移内容

---

## 1. 旧项目候选模块表

### 1.1 核心 §3.2 候选模块（可迁移）

| 文件路径 | 疑似功能 | §3.2 归属 | 禁止迁移 | 理由 |
|---------|---------|----------|---------|------|
| `code/step_extractor/step_extractor.py` | VerifierDrivenStepExtractor — 检查点序列构造 | ✅ 是 | ❌ 否 | 核心：检查点序列构造（step sequence construction） |
| `code/step_extractor/segmentation.py` | StructureParse — 结构解析与模板步骤生成 | ✅ 是 | ❌ 否 | 核心：检查点分段与结构解析 |
| `code/step_extractor/schema.py` | StepObject、RuleLibrary、ParseStatus 定义 | ✅ 是 | ❌ 否 | 核心：检查点对象模型与规则库接口 |
| `code/step_extractor/bridge_sql_pipeline.py` | SQL Pipeline 桥接 | ✅ 是 | ❌ 否 | 核心：SQL 解析管道集成 |
| `code/step_extractor/paper_based_step_extractor_reconstruction.py` | 论文驱动的重构实现 | ✅ 是 | ❌ 否 | 核心：检查点提取器完整实现 |
| `code/verifier/vsp_verifier.py` | VSP 四层验证器（语法→模式→语义→执行） | ✅ 是 | ❌ 否 | 核心：验证规则引擎（verification rule engine） |
| `code/verifier/constraint_rules.py` | 自动化 SQL 验证规则库生成 | ✅ 是 | ❌ 否 | 核心：语法约束、类型约束、执行端一致性 |
| `code/cpfc/dependency_extractor.py` | SQLDependencyExtractor — 依赖关系提取 | ✅ 是 | ❌ 否 | 核心：历史结构依赖集合 extraction of E_minus |
| `code/cpfc/sql_cpfc.py` | CPFC SQL 处理核心 | ✅ 是 | ❌ 否 | 核心：检查点级 SQL 特征提取 |
| `code/cpfc/__init__.py` | CPFC 模块入口 | ✅ 是 | ❌ 否 | 核心：模块组织 |
| `code/generation/candidate_generator.py` | 候选生成器（含扰动注入） | ✅ 是 | ❌ 否 | 核心：扰动响应记录 generation of R |
| `configs/experiment_config.yaml` | 实验配置（VSP、generation、state 参数） | ✅ 是 | ❌ 否 | 核心：冻结参数来源 |
| `configs/frozen_manifest_v1.0.yaml` | 冻结参数清单 | ✅ 是 | ❌ 否 | 核心：协议参数定义 |

### 1.2 禁止迁移模块（§3.3 及以后）

| 文件路径 | 疑似功能 | §3.2 归属 | 禁止迁移 | 理由 |
|---------|---------|----------|---------|------|
| `code/state/state_calculator.py` | 诊断特征工程（A_i,t, H_i,t, I+, I-） | ❌ 否 | ✅ 是 | §3.3 诊断特征工程，禁止迁移 |
| `code/state/parent_ablation.py` | 父消融计算 I_+/I_- | ❌ 否 | ✅ 是 | §3.3 消融研究，禁止迁移 |
| `code/dynamics/*.py` | 动力学模型、方程拟合 | ❌ 否 | ✅ 是 | §3.4 模型训练/递推状态，禁止迁移 |
| `scripts/exp003_*.py` | 动力学验证实验 | ❌ 否 | ✅ 是 | §3.4 训练相关，禁止迁移 |
| `scripts/exp010_*.py` | VSP 校准实验 | ❌ 否 | ✅ 是 | calibration/threshold selection，禁止迁移 |
| `scripts/exp021_*.py` | 风险记忆方向性 | ❌ 否 | ✅ 是 | §3.4 训练相关，禁止迁移 |
| `scripts/exp022_*.py` | 语义层重校准 | ❌ 否 | ✅ 是 | calibration，禁止迁移 |
| `scripts/exp023_*.py` | 门控 vs 步骤固定效应 | ❌ 否 | ✅ 是 | §3.4 训练相关，禁止迁移 |
| `scripts/exp024_*.py` | 金标准扩展 | ❌ 否 | ✅ 是 | heldout evaluation，禁止迁移 |
| `scripts/exp025_*.py` | 主分析/图表生成 | ❌ 否 | ✅ 是 | plotting/visualization，禁止迁移 |
| `scripts/generate_fig*.py` | 论文图表生成 | ❌ 否 | ✅ 是 | plotting/visualization，禁止迁移 |
| `scripts/run_exp*_main.py` | 实验运行器 | ❌ 否 | ✅ 是 | 实验编排（含训练/评估），禁止迁移 |
| `code/pipeline/experiment_pipeline.py` | 完整实验管道 | ❌ 否 | ✅ 是 | 包含训练/评估流程，禁止迁移 |

### 1.3 中性/待确认模块

| 文件路径 | 疑似功能 | §3.2 归属 | 禁止迁移 | 理由 |
|---------|---------|----------|---------|------|
| `code/llm/aliyun_api.py` | LLM API 调用封装 | ⚠️ 部分 | ❌ 否 | 仅用于生成候选/扰动，需确认是否属于 §3.2 生成逻辑 |
| `scripts/run_synthetic_validation.py` | 合成数据验证 | ⚠️ 部分 | ❌ 否 | 包含 verifier 调用，但属于验证实验 |
| `verify_tables_data.py` | 表格数据验证 | ⚠️ 部分 | ❌ 否 | 数据完整性检查，可能可复用 |

---

## 2. 新项目当前目录结构摘要

```
D:\SL-RDAF\
├── sl_rdaf\                      # 核心库（Phase 1-3）
│   ├── ablations\                # 消融实验（禁止迁移内容）
│   ├── calibration\              # 校准模块（禁止迁移内容）
│   ├── configs\                  # 配置文件
│   ├── data\                     # 数据管道
│   ├── diagnostics\              # 诊断模块
│   ├── evaluation\               # 评估模块（禁止迁移内容）
│   ├── model\                    # 模型定义（禁止迁移内容）
│   ├── scripts\                  # 运行脚本
│   └── training\                 # 训练模块（禁止迁移内容）
├── scripts\                      # 辅助脚本
│   ├── data_completion\          # 数据补全
│   └── diagnostics\              # 诊断脚本
├── data\
│   ├── 原始数据\                 # 原始数据集
│   └── data\                     # 处理后的数据（feature_manifest.json）
├── outputs\                      # 实验输出
│   ├── ablations\                # 消融结果
│   ├── calibration\              # 校准结果
│   ├── diagnostics\              # 诊断结果
│   ├── evaluation\               # 评估结果
│   ├── phase1\                   # Phase 1 输出
│   ├── phase2\                   # Phase 2 输出
│   └── training\                 # 训练结果
├── splits_60_40\                 # 60/40 划分结果
├── heldout\                      # heldout 数据
├── PASS\                         # 验证通过标记
└── Material\
    └── ExternalFalsifiableMeasurementforSubmission\  # 旧项目（只读）
```

**关键发现**：
- NEW_ROOT 已实现完整的 Phase 1-3 框架
- 包含训练、校准、评估、消融等完整流程
- **缺少独立的 §3.2 观测平面生成模块**（当前数据管道直接生成 model-ready tensors）
- 数据源 `data/data/` 包含 `feature_manifest.json`，但未发现独立的 step/observation_plane 输出

---

## 3. 已发现的最终冻结参数来源

### 3.1 来自旧项目（ExternalFalsifiableMeasurementforSubmission）

| 参数 | 旧值 | 来源文件 | 说明 |
|------|------|---------|------|
| `random_seed` | 42 | `configs/frozen_manifest_v1.0.yaml` | 全局随机种子 |
| `temperature` | 未明确 | `configs/experiment_config.yaml` 缺失 | 旧项目未冻结 temperature |
| `llm_model` | `qwen-turbo` | `configs/experiment_config.yaml` | 阿里云 Qwen Turbo |
| `llm_endpoint` | `https://dashscope.aliyuncs.com/...` | `configs/experiment_config.yaml` | 阿里云 API |
| `n_candidates_per_step` | 30 | `configs/experiment_config.yaml` (vsp) | VSP 候选数 |
| `verification_timeout` | 30s | `configs/experiment_config.yaml` | 验证超时 |
| `train_test_split` | [214, 320] | `configs/frozen_manifest_v1.0.yaml` | 40:60 划分 |
| `tau_g` | 0.3 | `configs/frozen_manifest_v1.0.yaml` | 门控工作点 |
| `N_min_eff` | 30 | `configs/frozen_manifest_v1.0.yaml` | 最小有效样本 |
| `ljung_box_lags` | 5 | `configs/frozen_manifest_v1.0.yaml` | Ljung-Box 滞后阶数 |
| `alpha_0` | 1.4426950408889634 | `configs/frozen_manifest_v1.0.yaml` | 理论值 ln(2)/ln(e) |
| `gate_params` | w_A=1.436, w_u=-0.338, b_g=-5.0 | `configs/frozen_manifest_v1.0.yaml` | 门控参数 |

### 3.2 来自新项目（SL-RDAF）

| 参数 | 新值 | 来源文件 | 说明 |
|------|------|---------|------|
| `seed` | 20260528 | `outputs/training/train_config_frozen.json` | 训练随机种子 |
| `seed` | 2026 | `scripts/run_bootstrap_ci.py` | Bootstrap 随机种子 |
| `train-dev` | 324 样本, 3,928 行 | `Material/SL-RDAF_algorithm_framework_phase1_phase2_phase3.md` | 训练集 |
| `cal-dev` | 214 样本, 2,571 行 | `Material/SL-RDAF_algorithm_framework_phase1_phase2_phase3.md` | 校准集 |
| `heldout` | 365 样本, 4,289 行 | `Material/SL-RDAF_algorithm_framework_phase1_phase2_phase3.md` | 测试集 |
| `total_samples` | 903 | `data/原始数据/dataset_warning_fixed/README_dataset_v1.0.md` | 总样本数 |
| `total_rows` | 10,788 | `outputs/diagnostics_4_2/agent_cluster_package/README_for_agent_cluster.md` | 总行数 |
| `dim_x_dir` | 5 | `outputs/training/train_config_frozen.json` | 方向通道维度 |
| `dim_x_res` | 11 | `outputs/training/train_config_frozen.json` | 残差通道维度 |
| `dim_s` | 8 | `outputs/training/train_config_frozen.json` | 状态维度 |
| `horizons` | [1, 2, 3] | `outputs/training/train_config_frozen.json` | 预警视野 |
| `lead_steps` | [1, 2, 3] | `outputs/training/train_config_frozen.json` | 提前步数 |

### 3.3 参数冲突与不一致

| 参数 | 旧值 | 新值 | 冲突位置 | 解决方案 |
|------|------|------|---------|---------|
| `random_seed` | 42 | 20260528 | `frozen_manifest_v1.0.yaml` vs `train_config_frozen.json` | **以新值为准**（20260528），旧值为通用默认值 |
| `train_test_split` | [214, 320] | [324, 214, 365] | `frozen_manifest_v1.0.yaml` vs `SL-RDAF_algorithm_framework...md` | **以新值为准**，旧值为二元划分，新值为三元划分（train-dev/cal-dev/heldout） |
| `temperature` | 未冻结 | 0（论文要求） | 旧项目缺失 | **需显式冻结为 0** |
| `llm_model` | qwen-turbo | 未明确 | 旧项目有，新项目缺失 | **需确认 SL-RDAF 使用的 LLM 版本** |
| `N, M` | 未明确 | 未明确 | 两项目均缺失 | **需从论文 §3.2 确认 verification repeats / N / M 固定值** |

---

## 4. 缺失或冲突参数清单

| 参数 | 状态 | 说明 |
|------|------|------|
| `temperature` | ❌ 缺失 | 论文要求 temperature=0，但旧项目 configs 中未明确冻结 |
| `LLM 版本` | ⚠️ 部分 | 旧项目为 `qwen-turbo`，新项目未明确，需确认 |
| `规则库版本` | ❌ 缺失 | 未找到 rule_library version 字段 |
| `扰动族定义` | ⚠️ 部分 | `configs/experiment_config.yaml` 有 `inject_ratio: 0.2`，但扰动族完整定义缺失 |
| `verification repeats` | ❌ 缺失 | 未找到 verification repeats 参数 |
| `N, M 固定值` | ❌ 缺失 | 未找到 N（验证重复次数）和 M（扰动次数）的明确定义 |
| `rule_library 版本号` | ❌ 缺失 | constraint_rules.py 无版本标记 |

---

## 5. 推荐迁移目标路径

```
D:\SL-RDAF\
├── src\                          # 迁移后的 §3.2 核心代码
│   ├── step\               # 检查点序列构造
│   │   ├── __init__.py
│   │   ├── extractor.py          # ← step_extractor.py (重命名)
│   │   ├── segmentation.py       # ← segmentation.py
│   │   ├── schema.py             # ← schema.py
│   │   └── sql_pipeline.py       # ← bridge_sql_pipeline.py (重命名)
│   ├── verification\             # 验证规则引擎
│   │   ├── __init__.py
│   │   ├── rule_engine.py        # ← vsp_verifier.py (重命名)
│   │   └── constraint_rules.py   # ← constraint_rules.py
│   ├── dependency\               # 历史结构依赖集合
│   │   ├── __init__.py
│   │   └── extractor.py          # ← dependency_extractor.py (重命名)
│   ├── perturbation\             # 扰动响应记录
│   │   ├── __init__.py
│   │   └── response_generator.py # ← candidate_generator.py (重命名)
│   └── observation_plane\        # 观测平面输出
│       ├── __init__.py
│       ├── jsonl_writer.py       # JSONL 输出
│       └── parquet_writer.py     # Parquet 输出
├── experiments\                  # 实验脚本（仅 §3.2 相关）
│   ├── generate_observation_planes.py
│   └── verify_step_sequence.py
├── tests\                        # 测试
│   ├── test_step_extractor.py
│   ├── test_verification_engine.py
│   ├── test_dependency_extractor.py
│   └── test_perturbation_response.py
└── configs\                      # 冻结配置
    ├── frozen_protocol.json      # ← FROZEN_PROTOCOL_MANIFEST.json
    └── observation_plane_config.yaml
```

---

## 6. 需要人工确认的问题

### 6.1 协议参数确认

1. **temperature**: 论文要求 temperature=0，但旧项目 configs 中未明确。是否确认所有 LLM 调用使用 temperature=0？
2. **LLM 版本**: SL-RDAF 论文使用的 LLM 版本是什么？旧项目使用 `qwen-turbo`，新项目未明确。
3. **规则库版本**: 是否需要为 constraint_rules.py 添加版本号？当前无版本标记。
4. **扰动族定义**: 完整的扰动族定义在哪里？`inject_ratio: 0.2` 是否足够？
5. **verification repeats / N / M**: 论文 §3.2 中 N 和 M 的固定值是多少？
6. **随机种子**: 使用 20260528（训练种子）还是 42（旧项目默认）？建议统一为 20260528。

### 6.2 迁移范围确认

1. **bridge_sql_pipeline.py**: 是否属于 §3.2 核心？还是属于数据预处理？
2. **candidate_generator.py**: 扰动生成是否属于 §3.2？还是属于 §3.3 特征工程的前置步骤？
3. **llm/aliyun_api.py**: LLM API 封装是否可迁移？还是应替换为新接口？

### 6.3 输出格式确认

1. **JSONL vs Parquet**: 观测平面输出应使用哪种格式？还是两者都生成？
2. **schema 定义**: 观测平面的 JSON schema 是否与论文符号一致？
3. **数据源**: 是否从 `data/data/` 读取已有数据生成观测平面，还是重新运行检查点提取？

### 6.4 命名体系确认

1. **Step vs Step**: 旧项目使用 `StepObject`，论文使用 `step`。是否统一为 `step`？
2. **Observation Plane vs Observation**: 旧项目未使用 `observation_plane` 术语。是否采用论文符号？
3. **E_minus vs dependency_edges**: 旧项目使用 `dependency_edges`，论文使用 `E_minus`。是否统一？

---

## 7. 论文与项目对应关系

### 7.1 旧项目论文

- **标题**: Beyond Endpoint Accuracy: Externally Verifiable Analysis of Neural Reasoning Degradation in Large Language Models
- **LaTeX 主文件**: `Material/ExternalFalsifiableMeasurementforSubmission/paper_sources/paper1.tex`
- **PDF 位置**: 未找到 paper1.pdf（仅找到 figures/ 下的图表 PDF）
- **状态**: Submitted to Information Sciences

### 7.2 新项目论文

- **标题**: Step-Level Multi-Horizon Degradation Analysis for LLM-Based Agent Systems in Industrial IoT
- **LaTeX 主文件**: 未找到（可能在 `Material/` 下，但未发现 .tex 文件）
- **PDF 位置**: 未找到
- **实验设计文档**: `Material/SL-RDAF 实验设计方案.md`
- **算法框架文档**: `Material/SL-RDAF_algorithm_framework_phase1_phase2_phase3.md`

### 7.3 §3.2 内容定位

**旧项目 paper1.tex §3.2 对应内容**：
- CPFC (Step-level Falsifiable Measurement)
- Verifier-Driven Step Extraction
- VSP (Verifier Stability Protocol)

**新项目论文 §3.2 对应内容**（根据实验设计方案）：
- 检查点序列构造
- 验证规则引擎
- 历史结构依赖集合
- 扰动响应记录
- 观测平面 O_i

---

## 8. 审计结论

### 8.1 可迁移模块（12 个核心文件）

1. `code/step_extractor/` 整个目录（5 个文件）
2. `code/verifier/` 整个目录（2 个文件）
3. `code/cpfc/` 核心文件（2 个文件）
4. `code/generation/candidate_generator.py`
5. `configs/experiment_config.yaml`（VSP/generation 部分）
6. `configs/frozen_manifest_v1.0.yaml`（协议参数部分）

### 8.2 禁止迁移模块（15+ 个文件）

- 所有 `code/state/` 目录（§3.3 诊断特征工程）
- 所有 `code/dynamics/` 目录（§3.4 模型训练）
- 所有 `scripts/exp003_*.py` 到 `exp025_*.py`（训练/评估/可视化）
- 所有 `scripts/generate_fig*.py`（可视化）
- `code/pipeline/experiment_pipeline.py`（完整实验管道）

### 8.3 关键缺失

- temperature=0 未显式冻结
- LLM 版本未在新项目中明确
- 规则库版本缺失
- 扰动族完整定义缺失
- verification repeats / N / M 未明确
- 观测平面输出格式未定义

### 8.4 下一步行动

1. **人工确认**第 6 节所有问题
2. **冻结参数**：生成 FROZEN_PROTOCOL_MANIFEST.json
3. **创建目录结构**：按照第 5 节推荐路径创建 src/、experiments/、tests/
4. **迁移代码**：复制并重命名第 8.1 节列出的文件
5. **重构命名**：统一使用论文符号（step、observation_plane 等）
6. **生成测试**：为每个迁移模块编写单元测试
7. **生成文档**：README.md、迁移报告

---

**审计完成时间**: 2026-06-03  
**审计人**: Qwen Code (Read-Only Mode)  
**状态**: ✅ 只读审计完成，未修改任何文件
