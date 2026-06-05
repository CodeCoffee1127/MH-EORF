"""
Observation plane assembly for Section 3.2.

Defines ObservationRecord and ObservationPlane dataclasses,
and provides observation plane assembly logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any

from .leakage import assert_no_forbidden_fields
from .checkpoints import build_step_sequence
from .verification import load_rule_library, verify_step_sequence
from .dependencies import extract_all_dependency_sets
from .perturbations import generate_perturbation_responses
from .io import dataclass_to_dict


@dataclass
class ObservationRecord:
    """Single observation record for a step."""

    p: object  # Step
    v: list  # List[VerificationResult]
    E_minus: list  # List[str]
    R: list  # List[PerturbationResponse]


@dataclass
class ObservationPlane:
    """Complete observation plane for a sample."""

    sample_id: str
    observation_plane: list[ObservationRecord]
    protocol_hash: str
    leakage_check: dict


def _group_verification_by_step(verification_results: list) -> dict[str, list]:
    """Group verification results by step_id."""
    v_map = {}
    for vr in verification_results:
        v_map.setdefault(vr.step_id, []).append(vr)
    return v_map


def _group_dependencies_by_step(dependency_sets: list) -> dict[str, object]:
    """Group dependency sets by step_id."""
    d_map = {}
    for ds in dependency_sets:
        d_map[ds.step_id] = ds
    return d_map


def _group_perturbations_by_step(perturbation_responses: list) -> dict[str, list]:
    """Group perturbation responses by step_id."""
    p_map = {}
    for pr in perturbation_responses:
        p_map.setdefault(pr.step_id, []).append(pr)
    return p_map


def build_observation_plane(
    sample: dict, context: dict, protocol
) -> ObservationPlane:
    """
    Build observation plane from raw sample data.

    Args:
        sample: Raw sample dictionary
        context: Construction context
        protocol: ObservationProtocol instance

    Returns:
        ObservationPlane instance
    """
    # 1. Input leakage scan
    assert_no_forbidden_fields(sample, context="input sample")

    # 2. Build step sequence
    sequence = build_step_sequence(sample, protocol)

    # 3. Build verification results
    rules = load_rule_library(protocol)
    verification_results = verify_step_sequence(sequence, context, protocol)

    # 4. Build dependency sets
    dependency_context = dict(context)
    dependency_context["verification_results"] = verification_results
    dependency_sets = extract_all_dependency_sets(sequence, dependency_context, protocol)

    # 5. Build perturbation responses
    perturbation_context = dict(context)
    perturbation_context["verification_results"] = verification_results
    perturbation_responses = generate_perturbation_responses(
        sequence=sequence,
        dependency_sets=dependency_sets,
        context=perturbation_context,
        rules=rules,
        protocol=protocol,
    )

    # 6. Assemble observation plane
    plane = assemble_observation_plane(
        sequence,
        verification_results,
        dependency_sets,
        perturbation_responses,
        protocol,
    )

    # 7. Final leakage scan
    plane_dict = dataclass_to_dict(plane)
    assert_no_forbidden_fields(plane_dict, context="observation plane output")

    return plane


def assemble_observation_plane(
    sequence,
    verification_results: list,
    dependency_sets: list,
    perturbation_responses: list,
    protocol,
) -> ObservationPlane:
    """
    Assemble observation plane from components.

    Args:
        sequence: StepSequence instance
        verification_results: List of VerificationResult instances
        dependency_sets: List of DependencySet instances
        perturbation_responses: List of PerturbationResponse instances
        protocol: ObservationProtocol instance

    Returns:
        ObservationPlane instance
    """
    # Build lookup maps
    step_map = {cp.step_id: cp for cp in sequence.steps}
    verification_map = _group_verification_by_step(verification_results)
    dependency_map = _group_dependencies_by_step(dependency_sets)
    perturbation_map = _group_perturbations_by_step(perturbation_responses)

    # Assemble records in t order
    records = []
    for cp in sequence.steps:
        cid = cp.step_id

        v_list = verification_map.get(cid, [])
        ds = dependency_map.get(cid)
        E_minus = ds.E_minus if ds else []
        R_list = perturbation_map.get(cid, [])

        # Validate R predecessors belong to E_minus
        for pr in R_list:
            if pr.perturbed_predecessor_id not in E_minus:
                raise ValueError(
                    f"Perturbation response {pr.perturbation_id} has predecessor "
                    f"{pr.perturbed_predecessor_id} not in E_minus of {cid}"
                )
            pred_cp = step_map.get(pr.perturbed_predecessor_id)
            if pred_cp and pred_cp.t >= cp.t:
                raise ValueError(
                    f"Perturbation response {pr.perturbation_id} has predecessor "
                    f"t={pred_cp.t} >= current t={cp.t}"
                )

        # Validate E_minus predecessors exist and are historical
        for pred_id in E_minus:
            pred_cp = step_map.get(pred_id)
            if not pred_cp:
                raise ValueError(f"E_minus contains non-existent step {pred_id}")
            if pred_cp.t >= cp.t:
                raise ValueError(
                    f"E_minus contains future step {pred_id} (t={pred_cp.t} >= {cp.t})"
                )

        record = ObservationRecord(
            p=cp,
            v=v_list,
            E_minus=E_minus,
            R=R_list,
        )
        records.append(record)

    # Leakage check (default: all false)
    leakage_check = {
        "future_step_used": False,
        "tau_used": False,
        "final_label_used": False,
        "horizon_label_used": False,
        "downstream_feature_used": False,
    }

    # Run leakage guard
    try:
        assert_no_forbidden_fields(
            {"sample_id": sequence.sample_id, "protocol_hash": protocol.protocol_hash},
            context="observation_plane_assembly",
        )
    except ValueError:
        leakage_check["downstream_feature_used"] = True

    return ObservationPlane(
        sample_id=sequence.sample_id,
        observation_plane=records,
        protocol_hash=protocol.protocol_hash,
        leakage_check=leakage_check,
    )
