"""Strict output validation against the official challenge contract."""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

from code.config import (
    ALLOWED_PHASES,
    ALLOWED_OPERATIONS_BY_PHASE,
    VALID_OPERATION_STATES,
    STATUS_CHOICES,
)


class ValidationError(Exception):
    pass


def validate_output_csv(
    csv_path: Path, expected_case_ids: List[str]
) -> Tuple[bool, List[str]]:
    """Validates the generated output CSV file against all challenge constraints.
    Returns (is_valid, list_of_error_messages).
    """
    errors = []
    if not csv_path.exists():
        return False, [f"Output file does not exist: {csv_path}"]

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header != ["case_id", "deletion_status", "steps_json"]:
            errors.append(
                f"Invalid header: expected ['case_id', 'deletion_status', 'steps_json'], got {header}"
            )

        rows = list(reader)

    if len(rows) != len(expected_case_ids):
        errors.append(
            f"Row count mismatch: expected {len(expected_case_ids)} rows, got {len(rows)}"
        )

    seen_case_ids = []
    sorted_expected = sorted(expected_case_ids)

    for i, row in enumerate(rows):
        line_no = i + 2
        if len(row) != 3:
            errors.append(f"Line {line_no}: Expected 3 columns, got {len(row)}")
            continue

        case_id, status, steps_json_str = row[0].strip(), row[1].strip(), row[2].strip()
        seen_case_ids.append(case_id)

        if status not in STATUS_CHOICES:
            errors.append(f"Line {line_no} ({case_id}): Invalid status '{status}'")

        try:
            steps = json.loads(steps_json_str)
        except Exception as e:
            errors.append(f"Line {line_no} ({case_id}): Failed to parse JSON: {e}")
            continue

        if not isinstance(steps, list):
            errors.append(f"Line {line_no} ({case_id}): steps_json must be a JSON array")
            continue

        if status == "NOT_APPLICABLE":
            if len(steps) != 0:
                errors.append(
                    f"Line {line_no} ({case_id}): NOT_APPLICABLE must have empty steps array [], got {len(steps)} steps"
                )
            continue

        # For COMPLETE or INCOMPLETE
        phase_sequence = []
        for step_idx, step in enumerate(steps):
            expected_step_no = step_idx + 1
            if not isinstance(step, dict):
                errors.append(
                    f"Line {line_no} ({case_id}) step {step_idx}: step is not an object"
                )
                continue

            required_keys = {
                "step_no",
                "phase",
                "system_id",
                "resource_id",
                "operation",
                "state",
                "evidence_id",
            }
            if set(step.keys()) != required_keys:
                errors.append(
                    f"Line {line_no} ({case_id}) step {expected_step_no}: expected keys {required_keys}, got {set(step.keys())}"
                )

            step_no = step.get("step_no")
            if step_no != expected_step_no:
                errors.append(
                    f"Line {line_no} ({case_id}): expected step_no {expected_step_no}, got {step_no}"
                )

            phase = step.get("phase")
            operation = step.get("operation")
            state = step.get("state")
            evidence_id = step.get("evidence_id", "")

            if phase not in ALLOWED_PHASES:
                errors.append(
                    f"Line {line_no} ({case_id}) step {expected_step_no}: invalid phase '{phase}'"
                )
            else:
                phase_sequence.append(phase)
                if operation not in ALLOWED_OPERATIONS_BY_PHASE.get(phase, []):
                    errors.append(
                        f"Line {line_no} ({case_id}) step {expected_step_no}: operation '{operation}' not allowed in phase '{phase}'"
                    )

            if operation in VALID_OPERATION_STATES:
                expected_state = VALID_OPERATION_STATES[operation]
                if state != expected_state:
                    errors.append(
                        f"Line {line_no} ({case_id}) step {expected_step_no}: operation '{operation}' requires state '{expected_state}', got '{state}'"
                    )
            else:
                errors.append(
                    f"Line {line_no} ({case_id}) step {expected_step_no}: unknown operation '{operation}'"
                )

            if status == "COMPLETE":
                if phase != "VERIFICATION":
                    errors.append(
                        f"Line {line_no} ({case_id}) step {expected_step_no}: COMPLETE cases must only contain VERIFICATION phase steps, found '{phase}'"
                    )
                if not evidence_id:
                    errors.append(
                        f"Line {line_no} ({case_id}) step {expected_step_no}: COMPLETE verification steps must cite non-empty evidence_id"
                    )
            elif status == "INCOMPLETE":
                if phase == "FINDING" and not evidence_id:
                    errors.append(
                        f"Line {line_no} ({case_id}) step {expected_step_no}: FINDING step must cite an evidence_id"
                    )
                elif phase in ("REMEDIATION", "VERIFICATION") and evidence_id != "":
                    errors.append(
                        f"Line {line_no} ({case_id}) step {expected_step_no}: future {phase} step must use empty evidence_id, got '{evidence_id}'"
                    )

        # Check phase ordering: FINDING before REMEDIATION before VERIFICATION
        phase_order_map = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}
        numeric_phases = [phase_order_map[p] for p in phase_sequence if p in phase_order_map]
        if numeric_phases != sorted(numeric_phases):
            errors.append(
                f"Line {line_no} ({case_id}): Phase sequence not properly ordered (FINDING -> REMEDIATION -> VERIFICATION): {phase_sequence}"
            )

    if seen_case_ids != sorted_expected:
        errors.append(
            f"Case IDs are not sorted or do not exactly match expected cases"
        )

    return len(errors) == 0, errors
