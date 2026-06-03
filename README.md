# SL-RDAF: Checkpoint-Level Multi-Horizon Reliability Diagnosis for LLM-Based Agent Systems in Industrial IoT

This repository contains the code package for constructing checkpoint-level observable representations used in the SL-RDAF study.

---

## Paper

Checkpoint-Level Multi-Horizon Reliability Diagnosis for LLM-Based Agent Systems in Industrial IoT  
Submitted to IEEE Internet of Things Journal.

*Author identities are withheld to maintain double-blind review integrity.*

---

## Scope

This repository focuses on **Section 3.2, Checkpoint-level Observable Representation**:

- checkpoint sequence construction;
- verification result generation;
- historical dependency set extraction;
- perturbation response record generation;
- observation-plane assembly.

**Out of scope** (not included in this repository):

- downstream diagnostic feature construction;
- verification entropy feature computation;
- recursive reliability model training;
- calibration;
- threshold selection;
- heldout evaluation;
- visualization scripts;
- original datasets or large intermediate artifacts.

---

## Experimental Methodology

The full study employs Text-to-SQL structured reasoning tasks as the experimental carrier. The Agent reasoning process for sample $i$ is represented as a checkpoint sequence $p_{i,1:T_i}$. At each checkpoint $p_{i,t}$, the system records the verification result $v_{i,t}$, historical dependency set $\mathcal{E}^{-}_{i,t}$, and perturbation response record $\mathcal{R}_{i,t}$. These observation planes are used to generate diagnostic metrics such as verification consistency, verification entropy, dependency polarity, and historical risk memory.

### Model Architecture

The main model retains a dual-channel design separating the **direction channel** and the **residual channel**. The deep nesting boundary is excluded from the main model input and is used only for subsequent complexity stratification analysis and case selection.

**Table 1(a): Main model input, state dimensions, and parameter scale**

| Channel | Dimension | Fields |
|---------|-----------|--------|
| $x^{dir}_{i,t}$ | 5 | $1-A_{i,t}$, $H_{i,t}$, $\rho_{i,t}$, $I^-_{i,t}$, $I^+_{i,t}$ |
| $x^{res}_{i,t}$ | 11 | $U_{i,t}$, $\Delta(1-A_{i,t})$, $\Delta H_{i,t}$, $\log(1+t)$, phase one-hot, complexity tier one-hot |
| $s_{i,t}$ | 8 | Recursive reliability state |
| **Parameters** | **167** | Learnable model weights |

The direction channel preserves variables with explicit risk directions, while the residual channel preserves local changes and context information. The recursive reliability state uses an 8-dimensional representation. The model contains 167 learnable weight parameters, corresponding to 10,788 full checkpoint observation rows (observation rows / parameter ratio $\approx 64.6$).

### Data Splits and Evaluation

The experiment uses three mutually exclusive subsets: **train-dev**, **cal-dev**, and **heldout**.

- **train-dev**: Used for learning model parameters, standardization parameters, and class weights.
- **cal-dev**: Used for fitting calibration mappings and freezing multi-horizon thresholds.
- **heldout**: Used exclusively for final evaluation under frozen rules.

External measurement diagnosis, early warning performance evaluation, and structural ablation are all conducted under the same observation and decision boundaries.

**Table 1(b): Data splits and multi-horizon label statistics**

| Split | Samples | Total Rows | h=1 Valid | h=1 Pos | h=1 Rate | h=2 Valid | h=2 Pos | h=2 Rate | h=3 Valid | h=3 Pos | h=3 Rate |
|-------|---------|------------|-----------|---------|----------|-----------|---------|----------|-----------|---------|----------|
| train-dev | 324 | 3,928 | 1,475 | 189 | 0.1281 | 1,315 | 310 | 0.2357 | 1,138 | 374 | 0.3286 |
| cal-dev | 214 | 2,571 | 973 | 127 | 0.1305 | 863 | 202 | 0.2341 | 735 | 235 | 0.3197 |
| heldout | 365 | 4,289 | 1,626 | 210 | 0.1292 | 1,436 | 339 | 0.2361 | 1,227 | 398 | 0.3244 |
| **Total** | **903** | **10,788** | **4,074** | **526** | **0.1291** | **3,614** | **851** | **0.2355** | **3,100** | **1,007** | **0.3248** |

The multi-horizon positive rate increases from 0.1291 at $h=1$ to 0.3248 at $h=3$. The label distributions across the three splits are consistent, supporting independent transfer evaluation on the heldout set.

---

## Observation Plane Definition

For sample *i*, the observation plane is represented as:

```
O_i = {(p_{i,t}, v_{i,t}, E^{-}_{i,t}, R_{i,t})}_{t=1}^{T_i}
```

where:

- *p_{i,t}*: checkpoint;
- *v_{i,t}*: verification result;
- *E^{-}_{i,t}*: historical dependency set;
- *R_{i,t}*: perturbation response record.

The observation plane uses only current and historical information available up to checkpoint *t*. It excludes future checkpoints, degradation labels, final execution labels, and downstream model predictions.

---

## Repository Structure

```
src/slrdaf/observation/
  checkpoints.py          — Checkpoint sequence construction
  verification.py         — Verification rule engine
  dependencies.py         — Historical dependency set extraction
  perturbations.py        — Perturbation response generation
  observation_plane.py    — Observation plane assembly
  protocol.py             — Protocol loading & validation
  io.py                   — JSONL I/O utilities
  leakage.py              — Leakage detection & forbidden-field scanning

experiments/
  build_observation_plane.py          — CLI builder (preview & dataset modes)
  validate_observation_plane.py       — CLI validator
  preview_checkpoint_sequences.py     — Preview checkpoint outputs
  preview_verification_results.py     — Preview verification outputs
  preview_dependency_sets.py          — Preview dependency outputs
  preview_perturbation_responses.py   — Preview perturbation outputs

schemas/                — JSON Schema definitions for all artifacts
configs/                — Frozen protocol configuration
tests/                  — Unit tests (64 tests, all passing)
docs/                   — Migration & assembly documentation
```

> **Note:** `data/`, `artifacts/`, `submission/`, and `Material/` are intentionally excluded from GitHub. Data artifacts are distributed via figshare (see [Data Availability](#data-availability)).

---

## Installation

```bash
git clone https://github.com/CodeCoffee1127/SL-RDAF.git
cd SL-RDAF

python -m venv .venv
.venv\Scripts\activate

pip install -U pip
pip install pytest pyyaml jsonschema
```

The core observation modules use the Python standard library where possible. `jsonschema` is optional but recommended for schema validation.

Dependencies are also listed in [`requirements.txt`](requirements.txt).

---

## Frozen Protocol

The observation-plane construction follows a frozen protocol to ensure deterministic, reproducible outputs.

| Parameter | Value | Status |
|-----------|-------|--------|
| `temperature` | `0` | Frozen |
| `random_seed` | `20260528` | Frozen |
| `protocol_hash` | `52e2ab6a1388caa639e49669054d22ab9af6fd10ea4d7f15d994538f43d49430` | Verified |
| `split policy` | train-dev / cal-dev / heldout | Frozen |
| **Full build status** | **903 samples, 3,553 checkpoints** | Deterministic regex-based segmentation |
| **Preview build status** | **5 samples, 21 checkpoints, 63 verification results, 21 dependency sets, 52 perturbation responses** | Verified |

### Unconfirmed Protocol Items

The following items remain **unconfirmed** in the local final protocol and are preserved as `null` in `FROZEN_PROTOCOL_MANIFEST.json`:

- `llm_version`: not confirmed in local final protocol (legacy candidate `qwen-turbo` not adopted as the final SL-RDAF LLM version);
- `rule_library_version`: not confirmed; tracked by derived provenance hash `legacy_rules_sha256_72b341a9063d`;
- `perturbation_family_version`: implementation draft / not final paper-declared version;
- `verification_repeats`, `N`, `M`: not confirmed in local final protocol.

See [`FROZEN_PROTOCOL_MANIFEST.json`](FROZEN_PROTOCOL_MANIFEST.json) and [`PROTOCOL_CONFLICTS.md`](PROTOCOL_CONFLICTS.md) for full details.

---

## Reproduction

### 1. Verify code compiles

```bash
python -m py_compile src\slrdaf\observation\*.py
pytest tests -q
```

Expected: all 64 tests pass; no compilation errors.

### 2. Build observation planes (full 903 samples)

```bash
python experiments\build_observation_plane.py ^
  --input data\data ^
  --output artifacts\observation_plane_full ^
  --protocol FROZEN_PROTOCOL_MANIFEST.json ^
  --source-mode dataset
```

This step reconstructs the checkpoint-level observation planes $O_i = \{(p_{i,t}, v_{i,t}, \mathcal{E}^{-}_{i,t}, \mathcal{R}_{i,t})\}_{t=1}^{T_i}$ for all 903 samples across the train-dev, cal-dev, and heldout splits. The full dataset contains 10,788 observation rows. The local deterministic build produces 3,553 checkpoints via regex-based segmentation; matching the full 10,788 rows requires AST-level extraction or downstream feature-stage artifacts. See [`FULL_BUILD_ATTEMPT_REPORT.md`](FULL_BUILD_ATTEMPT_REPORT.md) for details.

### 3. Downstream diagnostic modeling (out of scope for this repository)

The observation planes generated above serve as the foundation for the full multi-horizon reliability diagnosis pipeline:

- **Feature construction**: Derive verification consistency, verification entropy, dependency polarity, and historical risk memory from $O_i$.
- **Main model training**: Learn the 167-weight dual-channel model (direction channel $x^{dir}_{i,t}$ and residual channel $x^{res}_{i,t}$ with 8-dimensional recursive state $s_{i,t}$) on the **train-dev** split (324 samples, 3,928 rows).
- **Calibration & threshold freezing**: Fit calibration mappings and freeze multi-horizon thresholds on the **cal-dev** split (214 samples, 2,571 rows).
- **Final evaluation**: Run frozen-rule evaluation on the **heldout** split (365 samples, 4,289 rows). All external measurement diagnosis, early warning performance evaluation, and structural ablation are conducted under the same observation and decision boundaries.

The training, calibration, and evaluation code is not included in this §3.2-only repository. The provided observation-plane artifacts and protocol definitions are sufficient to reproduce the input representation for downstream experiments.

---

## Validation

```bash
python experiments\validate_observation_plane.py ^
  --input artifacts\observation_plane_full\observation_planes.jsonl ^
  --schemas schemas ^
  --manifest FROZEN_PROTOCOL_MANIFEST.json
```

Expected output: all records pass schema validation, zero forbidden-field violations, all leakage checks `false`.

---

## Data Availability

The GitHub repository does not include the original datasets, large intermediate artifacts, or figshare package contents.

Data and observation-plane artifacts are prepared separately for figshare under:

```
submission/figshare/SL-RDAF-data-v1
```

**DOI:** to be inserted after figshare reservation/publication.

The local figshare package contains **95 files** and is approximately **127 MB** after anonymization and checksum generation. The dataset comprises **903 samples** and **10,788 observation rows** (AST-level extraction) split into train-dev (324 samples), cal-dev (214 samples), and heldout (365 samples).

---

## Code Availability

The public code repository is:

https://github.com/CodeCoffee1127/SL-RDAF

---

## Boundary and Leakage Controls

This repository enforces strict boundaries to ensure reproducible, leakage-free observation-plane construction:

- **No LLM calls** during reproducible construction;
- **No original data** committed to GitHub;
- **No final labels**, `tau_i`, endpoint accuracy, or horizon labels in observation planes;
- `unverifiable=True` is preserved and is **not** forced to `false`;
- Perturbation payloads are stored as **SHA-256 hashes or safe summaries only**.

See [`CODE_BOUNDARY_AUDIT.md`](CODE_BOUNDARY_AUDIT.md) and [`leakage.py`](src/slrdaf/observation/leakage.py) for the complete forbidden-field list and audit results.

---

## Reports

The following migration and audit reports are included in the repository:

- [`DELIVERY_SUMMARY.md`](DELIVERY_SUMMARY.md) — Delivery overview & status
- [`DELIVERY_MANIFEST.json`](DELIVERY_MANIFEST.json) — Machine-readable delivery manifest
- [`FROZEN_PROTOCOL_MANIFEST.json`](FROZEN_PROTOCOL_MANIFEST.json) — Frozen protocol definition
- [`PROTOCOL_CONFLICTS.md`](PROTOCOL_CONFLICTS.md) — Protocol conflict resolution log
- [`PROTOCOL_FREEZE_REPORT.md`](PROTOCOL_FREEZE_REPORT.md) — Protocol freeze evidence
- [`FULL_BUILD_ATTEMPT_REPORT.md`](FULL_BUILD_ATTEMPT_REPORT.md) — Full build attempt results
- [`CODE_BOUNDARY_AUDIT.md`](CODE_BOUNDARY_AUDIT.md) — Code boundary audit results
- [`GITHUB_RELEASE_AUDIT.md`](GITHUB_RELEASE_AUDIT.md) — Pre-release audit & .gitignore rationale
- [`CHECKPOINT_MIGRATION_REPORT.md`](CHECKPOINT_MIGRATION_REPORT.md) — Checkpoint extraction migration
- [`VERIFICATION_MIGRATION_REPORT.md`](VERIFICATION_MIGRATION_REPORT.md) — Verification engine migration
- [`DEPENDENCY_MIGRATION_REPORT.md`](DEPENDENCY_MIGRATION_REPORT.md) — Dependency extraction migration
- [`PERTURBATION_MIGRATION_REPORT.md`](PERTURBATION_MIGRATION_REPORT.md) — Perturbation response migration
- [`OBSERVATION_PLANE_BUILD_REPORT.md`](OBSERVATION_PLANE_BUILD_REPORT.md) — Observation plane assembly report
- [`MIGRATION_AUDIT.md`](MIGRATION_AUDIT.md) — Initial migration audit

Selected migration reports are included when they do not contain sensitive local information. Full local reports are retained in the delivery package.

---

## Citation

If you use this repository, please cite the associated paper once published.

BibTeX placeholder:

```bibtex
@article{slrdaf2026,
  title={Checkpoint-Level Multi-Horizon Reliability Diagnosis for LLM-Based Agent Systems in Industrial IoT},
  journal={IEEE Internet of Things Journal},
  year={2026},
  note={Submitted}
}
```

---

## License

License to be confirmed before publication.
