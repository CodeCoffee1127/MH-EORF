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
| `protocol_hash` | `cfbcf95275899c462a6694b240df3f9679a0051a061403f27e94c041c816afaf` | Verified |
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

### 2. Preview-mode build (5 samples)

```bash
python experiments\build_observation_plane.py ^
  --input data\data ^
  --output artifacts\observation_plane ^
  --protocol FROZEN_PROTOCOL_MANIFEST.json ^
  --source-mode preview
```

Preview mode requires intermediate preview artifacts generated during migration validation. These artifacts are not stored in GitHub and are provided in the data package when available.

### 3. Dataset-mode build (full 903 samples)

```bash
python experiments\build_observation_plane.py ^
  --input data\data ^
  --output artifacts\observation_plane_full ^
  --protocol FROZEN_PROTOCOL_MANIFEST.json ^
  --source-mode dataset
```

Dataset mode attempts to reconstruct observation planes from local data files. In the final local delivery, dataset mode produced **903 samples and 3,553 checkpoint records** using deterministic regex-based segmentation. This differs from the **10,788 downstream observation rows** referenced in the broader experimental pipeline; matching that count may require AST-level extraction or downstream feature-stage artifacts not included in this §3.2-only repository. See [`FULL_BUILD_ATTEMPT_REPORT.md`](FULL_BUILD_ATTEMPT_REPORT.md) for details.

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

The local figshare package contains **95 files** and is approximately **127 MB** after anonymization and checksum generation.

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
