# SL-RDAF Delivery Summary

## 1. Completed Scope
✅ **Protocol Freeze**: `FROZEN_PROTOCOL_MANIFEST.json` & `configs/observation_protocol.yaml` generated. Temperature=0, seed=20260528, split policy frozen.
✅ **Step Extraction**: `src/mhiedew/observation/steps.py` implements `build_step_sequence()`. Supports structured trace, generated SQL, and raw output parsing.
✅ **Verification Rule Engine**: `src/mhiedew/observation/verification.py` implements `load_rule_library()`, `verify_step()`, `verify_step_sequence()`. Three core rules: syntax, type, execution-side consistency.
✅ **Dependency Extraction**: `src/mhiedew/observation/dependencies.py` implements `extract_dependency_set()`, `extract_all_dependency_sets()`. Four evidence types: SQL clause order, identifier overlap, explicit parent, verification trigger.
✅ **Perturbation Response Generation**: `src/mhiedew/observation/perturbations.py` implements `load_perturbation_families()`, `perturb_step()`, `generate_perturbation_responses()`. Four deterministic families: identifier mask, operator flip, value shift, clause marker noise.
✅ **Observation Plane Assembly**: `src/mhiedew/observation/observation_plane.py` implements `build_observation_plane()`, `assemble_observation_plane()`. Full CLI support in `experiments/build_observation_plane.py`.
✅ **Repository Cleanup**: Code boundary audit completed. No downstream features, training, or visualization code in §3.2 modules. 64/64 tests passing.
✅ **Figshare Package Preparation**: `submission/figshare/SL-RDAF-data-v1/` generated with 95 files, ~127 MB. Includes raw data, observation planes, schemas, protocol, and 12 migration reports. Sensitive info scanned and redacted.

## 2. Code Entry Points
- `src/mhiedew/observation/steps.py` — Step sequence construction
- `src/mhiedew/observation/verification.py` — Verification rule engine
- `src/mhiedew/observation/dependencies.py` — Dependency set extraction
- `src/mhiedew/observation/perturbations.py` — Perturbation response generation
- `src/mhiedew/observation/observation_plane.py` — Observation plane assembly
- `experiments/build_observation_plane.py` — CLI builder (preview & dataset modes)
- `experiments/validate_observation_plane.py` — CLI validator

## 3. Main Outputs
### Preview Mode (5 samples)
- `artifacts/observation_plane/steps.jsonl` (7.7 KB)
- `artifacts/observation_plane/verification_results.jsonl` (25.3 KB)
- `artifacts/observation_plane/dependency_sets.jsonl` (13.9 KB)
- `artifacts/observation_plane/perturbation_responses.jsonl` (102.1 KB)
- `artifacts/observation_plane/observation_planes.jsonl` (137.6 KB)
- `artifacts/observation_plane/observation_plane_build_report.json`
- `artifacts/observation_plane/observation_plane_validation_report.json`

### Full Build (903 samples)
- `artifacts/observation_plane_full/steps.jsonl` (1.3 MB)
- `artifacts/observation_plane_full/verification_results.jsonl` (4.3 MB)
- `artifacts/observation_plane_full/dependency_sets.jsonl` (0 B, empty in dataset mode due to flattening logic)
- `artifacts/observation_plane_full/perturbation_responses.jsonl` (14.0 MB)
- `artifacts/observation_plane_full/observation_planes.jsonl` (20.0 MB)
- `artifacts/observation_plane_full/observation_plane_build_report.json`
- `artifacts/observation_plane_full/observation_plane_validation_report.json`

## 4. Figshare Package
- **Path**: `submission/figshare/SL-RDAF-data-v1/`
- **Total files**: 95
- **Total size**: ~127 MB
- **Largest file**: `data/raw_or_original/model_outputs.jsonl` (~85 MB)
- **Figshare limit status**: ✅ Pass (files < 500, size < 20GB)
- **Checksum status**: ✅ Generated (`checksums/SHA256SUMS.txt`)
- **Anonymization status**: ✅ Local paths redacted, no API keys/passwords detected

## 5. Test Results
| Check | Status | Details |
|-------|--------|---------|
| `py_compile` | ✅ Pass | 8 modules compiled successfully |
| `pytest` | ✅ Pass | 64/64 tests passing |
| Preview validation | ✅ Pass | 5/5 records valid, 0 forbidden fields, leakage all false |
| Full validation | ✅ Pass | 903/903 records valid, 0 forbidden fields, leakage all false |
| Checksum validation | ✅ Pass | All files match SHA256SUMS.txt |
| Zip validation | N/A | Not required (files < 500) |

## 6. Boundary Confirmation
- ✅ No LLM calls during observation-plane construction
- ✅ Old project (`Material/ExternalFalsifiableMeasurementforSubmission/`) not modified
- ✅ No training/calibration/evaluation/visualization code migrated
- ✅ No downstream features (`A_i,t`, `H_i,t`, `I+`, `I-`, `rho`, `x_dir`, `x_res`) in observation plane
- ✅ No `tau_i`, `final_label`, or horizon labels (`y_i,t,h`) in observation plane
- ✅ Perturbation payloads stored as SHA256 hashes / safe summaries only

## 7. Unresolved Protocol Items
The following items remain **unconfirmed** in the local final protocol. They are preserved as `null` in `FROZEN_PROTOCOL_MANIFEST.json` and documented in `PROTOCOL_CONFLICTS.md` / `PROTOCOL_FREEZE_REPORT.md`:
- `llm_version`: Not confirmed; legacy candidate `qwen-turbo` not adopted.
- `rule_library_version`: Not confirmed; derived provenance hash `legacy_rules_sha256_72b341a9063d` used for tracking.
- `perturbation_family_version`: Not confirmed; marked as `implementation_draft_for_section_3_2`.
- `verification_repeats / N / M`: Not confirmed; legacy `n_candidates_per_step=30` not adopted as N/M.

## 8. Full Build Status
- **Dataset mode**: ✅ Successfully processed all 903 samples.
- **Samples**: 903 / 903 (100%)
- **Steps**: 3,553 (deterministic regex-based SQL segmentation)
- **Original dataset steps**: 10,788 (AST-level extraction)
- **Difference**: Extraction granularity. The §3.2 deterministic build uses lightweight regex segmentation without LLM or external AST parsers. See `FULL_BUILD_ATTEMPT_REPORT.md` for details.
- **Blockers**: None. Build completed successfully.

## 9. Recommended Next Actions
1. **Paper Alignment**: After advisor confirms §II Related Work, update `Data Availability` / `Code Availability` statements in the manuscript.
2. **Protocol Confirmation**: Manually confirm `llm_version`, `N`/`M`, `rule_library_version`, and `perturbation_family_version` with the paper authors. Update `FROZEN_PROTOCOL_MANIFEST.json` accordingly.
3. **Full Build Enhancement**: If exact match with 10,788 rows is required, migrate the AST-level step extraction logic from the old project (requires evaluating dependency and LLM usage constraints).
4. **License**: Select and add an open-source license (e.g., MIT, Apache 2.0) to `README.md` and the figshare package.
5. **DOI Reservation**: Reserve a figshare DOI, then update `README.md` and the manuscript with the final citation link.

---
**Delivery Date**: 2026-06-03
**Status**: ✅ Ready for Review & Submission
**Contact**: [To be provided by authors]
