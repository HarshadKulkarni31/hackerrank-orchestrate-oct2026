"""Strict output validation against the official challenge contract."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Set

from code.config import (
    ALLOWED_PHASES,
    ALLOWED_OPERATIONS_BY_PHASE,
    VALID_OPERATION_STATES,
    STATUS_CHOICES,
)


class ValidationError(Exception):
    pass


def validate_output_csv(
    csv_path: Path,
    expected_case_ids: List[str],
    dataset_dir: Optional[Path] = None,
) -> Tuple[bool, List[str]]:
    """Validates the generated output CSV file against all challenge constraints.
    Verifies schemas, allowed operations, phases, evidence grounding, temporal cutoff,
    subsystem operation constraints, and decision consistency.
    Returns (is_valid, list_of_error_messages).
    """
    errors = []
    if not csv_path.exists():
        return False, [f"Output file does not exist: {csv_path}"]

    if dataset_dir is None:
        dataset_dir = Path("dataset")

    # 1. Load Ground Truth Evidence Metadata for Grounding & Temporal Checks
    valid_evidence_ids: Set[str] = set()
    evidence_timestamps: Dict[str, datetime] = {}
    case_audit_times: Dict[str, datetime] = {}

    ev_files_csv = dataset_dir / "evidence_files.csv"
    if ev_files_csv.exists():
        with open(ev_files_csv, mode="r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                fid = r["file_id"]
                valid_evidence_ids.add(fid)
                if r.get("captured_at"):
                    try:
                        evidence_timestamps[fid] = datetime.fromisoformat(
                            r["captured_at"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

    act_csv = dataset_dir / "system_activity.csv"
    if act_csv.exists():
        with open(act_csv, mode="r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                aid = r["activity_id"]
                valid_evidence_ids.add(aid)
                if r.get("event_time"):
                    try:
                        evidence_timestamps[aid] = datetime.fromisoformat(
                            r["event_time"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

    audit_csv = dataset_dir / "user_audit_log.csv"
    if audit_csv.exists():
        with open(audit_csv, mode="r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                valid_evidence_ids.add(r["audit_id"])

    # Load case audit cutoff timestamps
    for req_filename in ("deletion_requests.csv", "sample_deletion_requests.csv"):
        req_csv = dataset_dir / req_filename
        if req_csv.exists():
            with open(req_csv, mode="r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    if r.get("case_id") and r.get("audit_at"):
                        try:
                            case_audit_times[r["case_id"]] = datetime.fromisoformat(
                                r["audit_at"].replace("Z", "+00:00")
                            )
                        except Exception:
                            pass

    # 2. Read and Validate Output CSV Structure
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

        # Consistency checks for COMPLETE / INCOMPLETE
        if status == "COMPLETE" and len(steps) == 0:
            errors.append(
                f"Line {line_no} ({case_id}): COMPLETE case must contain at least one verification step"
            )
        elif status == "INCOMPLETE" and not any(isinstance(s, dict) and s.get("phase") == "FINDING" for s in steps):
            errors.append(
                f"Line {line_no} ({case_id}): INCOMPLETE case must contain at least one FINDING step"
            )

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
            system_id = step.get("system_id")
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

            # Subsystem Specific Modeling Checks
            if system_id == "integration_service":
                if operation == "VERIFY_RECORD_ABSENT":
                    errors.append(
                        f"Line {line_no} ({case_id}) step {expected_step_no}: integration_service cannot use VERIFY_RECORD_ABSENT, must use VERIFY_DATA_FLOW_DISABLED"
                    )
            elif system_id == "backup_service":
                if operation == "VERIFY_RECORD_ABSENT":
                    errors.append(
                        f"Line {line_no} ({case_id}) step {expected_step_no}: backup_service cannot use VERIFY_RECORD_ABSENT, must use VERIFY_RESTORE_BLOCKED or VERIFY_RECORD_PRESENT"
                    )

            # Evidence Grounding & Temporal Checks
            if evidence_id:
                if valid_evidence_ids and evidence_id not in valid_evidence_ids:
                    errors.append(
                        f"Line {line_no} ({case_id}) step {expected_step_no}: cited evidence_id '{evidence_id}' does not exist in participant evidence files, activities, or audit logs"
                    )
                if case_id in case_audit_times and evidence_id in evidence_timestamps:
                    audit_cutoff = case_audit_times[case_id]
                    ev_captured_at = evidence_timestamps[evidence_id]
                    if ev_captured_at > audit_cutoff:
                        errors.append(
                            f"Line {line_no} ({case_id}) step {expected_step_no}: cited evidence '{evidence_id}' captured at {ev_captured_at.isoformat()} is AFTER case audit_at {audit_cutoff.isoformat()}"
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
