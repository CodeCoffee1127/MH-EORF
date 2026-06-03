"""
Test schema files are valid JSON and don't contain forbidden fields.
"""

import json
import sys
from pathlib import Path


def test_schema_files_exist_and_valid():
    """Test that all schema files exist and are valid JSON."""
    schema_dir = Path(__file__).resolve().parents[1] / "schemas"

    schema_files = [
        "checkpoint.schema.json",
        "verification_result.schema.json",
        "dependency_set.schema.json",
        "perturbation_response.schema.json",
        "observation_plane.schema.json",
        "observation_protocol.schema.json",
    ]

    for name in schema_files:
        p = schema_dir / name
        assert p.exists(), f"Schema file missing: {p}"

        # Parse JSON
        obj = json.loads(p.read_text(encoding="utf-8"))

        # Check required fields
        assert "$schema" in obj, f"{name} missing $schema"
        assert "properties" in obj, f"{name} missing properties"

    print(f"✓ test_schema_files_exist_and_valid passed ({len(schema_files)} files)")


def test_no_forbidden_fields_in_schema():
    """Test that schema properties don't contain forbidden fields."""
    schema_dir = Path(__file__).resolve().parents[1] / "schemas"

    # Forbidden field names (downstream task indicators)
    forbidden = {
        "A_i_t", "H_i_t", "I_plus", "I_minus", "Inec", "rho",
        "x_dir", "x_res", "s_i_t", "delta_s_i_t",
        "Q", "q", "calibrated_risk", "prediction",
        "tau", "tau_i", "first_degradation",
        "final_label", "endpoint_accuracy", "execution_accuracy",
        "y_i_t_h", "y_h1", "y_h2", "y_h3",
    }

    schema_files = list(schema_dir.glob("*.schema.json"))

    for sf in schema_files:
        obj = json.loads(sf.read_text(encoding="utf-8"))
        properties = obj.get("properties", {})

        for prop_name in properties.keys():
            assert prop_name not in forbidden, \
                f"Forbidden field '{prop_name}' found in {sf.name}"

    print(f"✓ test_no_forbidden_fields_in_schema passed ({len(schema_files)} files)")


if __name__ == "__main__":
    test_schema_files_exist_and_valid()
    test_no_forbidden_fields_in_schema()
    print("\nAll schema tests passed!")
