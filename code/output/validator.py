"""Strict output validation against the official challenge contract."""

import csv
import json
import re
from datetime import datetime, timezone
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
    evidence_origins: Dict[str, str] = {}
    activity_systems: Dict[str, str] = {}
    activity_resources: Dict[str, str] = {}
    case_audit_times: Dict[str, datetime] = {}

    origin_to_systems: Dict[str, Set[str]] = {
        "account_admin_portal": {"support_platform", "account_service"},
        "account_history_service": {"export_service"},
        "analytics_platform": {"analytics_platform"},
        "backup_service": {"backup_service"},
        "central_observability_export": {"security_service", "backup_service", "account_service", "search_service", "support_platform", "export_service", "integration_service", "analytics_platform"},
        "customer_account_failover_replica_capture": {"account_service"},
        "customer_account_service": {"security_service", "backup_service", "account_service", "search_service", "support_platform", "export_service", "integration_service", "analytics_platform"},
        "customer_data_failover_replica_capture": {"security_service"},
        "customer_data_inventory_capture": {"security_service", "backup_service", "account_service", "search_service", "support_platform", "export_service", "integration_service"},
        "customer_data_read_replica_capture": {"security_service", "account_service", "search_service", "support_platform", "export_service", "analytics_platform"},
        "customer_data_regional_replicas_capture": {"security_service", "account_service", "search_service", "support_platform", "export_service", "analytics_platform"},
        "customer_data_reporting_replica_capture": {"security_service", "account_service", "search_service", "support_platform", "export_service", "analytics_platform"},
        "customer_export_service": {"security_service", "backup_service", "account_service", "search_service", "support_platform", "export_service", "integration_service", "analytics_platform"},
        "customer_search_primary_capture": {"search_service"},
        "downstream_delivery_service": {"security_service", "backup_service", "account_service", "search_service", "support_platform", "integration_service", "analytics_platform"},
        "export_service": {"export_service"},
        "identity_service": {"identity_service"},
        "integration_admin": {"integration_service"},
        "integration_management_service": {"security_service", "account_service", "search_service", "support_platform", "integration_service", "analytics_platform"},
        "legal_retention_service": {"legal_service", "security_service"},
        "marketing_platform": {"marketing_platform"},
        "records_assurance_snapshot_bundle": {"security_service", "identity_service", "account_service", "search_service", "analytics_platform"},
        "search_index_admin": {"search_service"},
        "search_index_service": {"security_service", "backup_service", "account_service", "search_service", "support_platform", "integration_service", "analytics_platform"},
        "security_audit_service": {"security_service"},
        "security_service": {"security_service", "export_service"},
        "service_readback_logs": {"security_service", "backup_service", "account_service", "search_service", "support_platform", "export_service", "integration_service", "analytics_platform"},
        "service_resource_export": {"security_service", "backup_service", "account_service", "search_service", "support_platform", "export_service", "integration_service", "analytics_platform"},
        "support_platform": {"support_platform"},
    }

    ev_files_csv = dataset_dir / "evidence_files.csv"
    if ev_files_csv.exists():
        with open(ev_files_csv, mode="r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                fid = r["file_id"]
                valid_evidence_ids.add(fid)
                if r.get("origin"):
                    evidence_origins[fid] = r["origin"]
                if r.get("captured_at"):
                    try:
                        evidence_timestamps[fid] = datetime.fromisoformat(
                            r["captured_at"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

    activity_details: Dict[str, str] = {}
    act_csv = dataset_dir / "system_activity.csv"
    if act_csv.exists():
        with open(act_csv, mode="r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                aid = r["activity_id"]
                valid_evidence_ids.add(aid)
                if r.get("target_system"):
                    activity_systems[aid] = r["target_system"]
                if r.get("resource_id"):
                    activity_resources[aid] = r["resource_id"]
                if r.get("details"):
                    activity_details[aid] = r["details"]
                if r.get("event_time"):
                    try:
                        evidence_timestamps[aid] = datetime.fromisoformat(
                            r["event_time"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

    user_id_set: Set[str] = set()
    email_to_user: Dict[str, str] = {}
    user_to_emails: Dict[str, Set[str]] = {}
    ident_csv = dataset_dir / "user_identities.csv"
    if ident_csv.exists():
        with open(ident_csv, mode="r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                u = r["user_id"]
                em = r["email"].lower()
                user_id_set.add(u)
                email_to_user[em] = u
                user_to_emails.setdefault(u, set()).add(em)

    audit_csv = dataset_dir / "user_audit_log.csv"
    if audit_csv.exists():
        with open(audit_csv, mode="r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                valid_evidence_ids.add(r["audit_id"])
                u = r.get("user_id")
                if u:
                    user_id_set.add(u)
                old_val = (r.get("old_value") or "").lower()
                new_val = (r.get("new_value") or "").lower()
                if u and "@" in old_val:
                    email_to_user[old_val] = u
                    user_to_emails.setdefault(u, set()).add(old_val)
                if u and "@" in new_val:
                    email_to_user[new_val] = u
                    user_to_emails.setdefault(u, set()).add(new_val)

    # Load case audit cutoff timestamps & subjects
    case_user_ids: Dict[str, str] = {}
    case_emails: Dict[str, Set[str]] = {}
    for req_filename in ("deletion_requests.csv", "sample_deletion_requests.csv"):
        req_csv = dataset_dir / req_filename
        if req_csv.exists():
            with open(req_csv, mode="r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    cid = r.get("case_id")
                    if not cid:
                        continue
                    if r.get("audit_at"):
                        try:
                            case_audit_times[cid] = datetime.fromisoformat(
                                r["audit_at"].replace("Z", "+00:00")
                            )
                        except Exception:
                            pass
                    req_em = (r.get("email") or "").lower()
                    u = email_to_user.get(req_em)
                    if u:
                        case_user_ids[cid] = u
                        case_emails[cid] = set(user_to_emails.get(u, {req_em}))
                    else:
                        case_emails[cid] = {req_em} if req_em else set()

    file_resources: Dict[str, Set[str]] = {}
    file_users: Dict[str, Set[str]] = {}
    file_emails: Dict[str, Set[str]] = {}
    try:
        from code.evidence.dispatcher import EvidenceDispatcher
        dispatcher = EvidenceDispatcher(dataset_dir=dataset_dir)
        ev_manifest_rows = []
        if ev_files_csv.exists():
            with open(ev_files_csv, mode="r", encoding="utf-8") as f:
                ev_manifest_rows = list(csv.DictReader(f))
        dispatcher.load_all(ev_manifest_rows)
        for rec in dispatcher.records:
            fid = rec.evidence_id
            if rec.resource_id:
                file_resources.setdefault(fid, set()).add(rec.resource_id)
            if rec.user_id:
                file_users.setdefault(fid, set()).add(rec.user_id)
            if rec.email:
                file_emails.setdefault(fid, set()).add(rec.email.lower())
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
            resource_id = step.get("resource_id")
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

                # Semantic relevance checks: validate activity target system, resource, and subject
                if evidence_id in activity_systems:
                    act_sys = activity_systems[evidence_id]
                    allowed_act_sys = {act_sys}
                    if act_sys == "object_storage":
                        allowed_act_sys.add("support_platform")
                    if system_id and act_sys and system_id not in allowed_act_sys:
                        errors.append(
                            f"Line {line_no} ({case_id}) step {expected_step_no}: cited activity '{evidence_id}' targets system '{act_sys}', not claimed system '{system_id}'"
                        )
                    act_res = activity_resources.get(evidence_id)
                    if resource_id and act_res and resource_id != act_res:
                        errors.append(
                            f"Line {line_no} ({case_id}) step {expected_step_no}: cited activity '{evidence_id}' concerns resource '{act_res}', not claimed resource '{resource_id}'"
                        )
                    details = activity_details.get(evidence_id, "")
                    u_match = re.search(r"\b(user_\d+)\b", details)
                    case_u = case_user_ids.get(case_id)
                    if case_u and u_match and u_match.group(1) != case_u:
                        errors.append(
                            f"Line {line_no} ({case_id}) step {expected_step_no}: cited activity '{evidence_id}' concerns subject '{u_match.group(1)}', not case subject '{case_u}'"
                        )

                # Validate dedicated evidence file origin and subject/resource relevance
                if evidence_id in evidence_origins:
                    origin = evidence_origins[evidence_id]
                    allowed_sys = origin_to_systems.get(origin)
                    if allowed_sys and system_id not in allowed_sys:
                        errors.append(
                            f"Line {line_no} ({case_id}) step {expected_step_no}: evidence '{evidence_id}' from origin '{origin}' is not relevant to system '{system_id}'"
                        )

                    # Subject & Resource relevance check for evidence files
                    if evidence_id in file_resources or evidence_id in file_users:
                        res_set = file_resources.get(evidence_id, set())
                        u_set = file_users.get(evidence_id, set())
                        em_set = file_emails.get(evidence_id, set())
                        case_u = case_user_ids.get(case_id)
                        case_em = case_emails.get(case_id, set())

                        matches_resource = bool(resource_id and resource_id in res_set)
                        matches_user = bool((case_u and case_u in u_set) or (case_em and bool(case_em & em_set)))

                        if phase == "FINDING":
                            if not matches_resource and not matches_user:
                                errors.append(
                                    f"Line {line_no} ({case_id}) step {expected_step_no}: FINDING step cites evidence '{evidence_id}' which does not contain claimed resource '{resource_id}' or subject '{case_u}'"
                                )
                        elif phase == "VERIFICATION":
                            if operation in ("VERIFY_RECORD_PRESENT", "VERIFY_RECORD_REDACTED", "VERIFY_RECORD_ANONYMIZED"):
                                if not matches_resource and not matches_user:
                                    errors.append(
                                        f"Line {line_no} ({case_id}) step {expected_step_no}: verification '{operation}' cites evidence '{evidence_id}' which does not contain claimed resource '{resource_id}' or subject '{case_u}'"
                                    )
                            elif operation == "VERIFY_RECORD_ABSENT":
                                if matches_resource:
                                    rec_states = [r.state for r in dispatcher.find_records_by_resource_id(resource_id, case_audit_times.get(case_id, datetime.max.replace(tzinfo=timezone.utc)))]
                                    if any(st == "PRESENT" for st in rec_states):
                                        errors.append(
                                            f"Line {line_no} ({case_id}) step {expected_step_no}: VERIFY_RECORD_ABSENT cites evidence '{evidence_id}' where resource '{resource_id}' is PRESENT"
                                        )
                                elif not matches_user:
                                    snapshot_origins = {
                                        "customer_account_failover_replica_capture",
                                        "customer_account_service",
                                        "customer_data_failover_replica_capture",
                                        "customer_data_read_replica_capture",
                                        "customer_data_regional_replicas_capture",
                                        "customer_data_reporting_replica_capture",
                                        "customer_search_primary_capture",
                                        "records_assurance_snapshot_bundle",
                                        "service_resource_export",
                                        "service_readback_logs",
                                        "central_observability_export",
                                    }
                                    if origin not in snapshot_origins or (u_set and len(u_set) == 1 and not (case_u in u_set)):
                                        errors.append(
                                            f"Line {line_no} ({case_id}) step {expected_step_no}: VERIFY_RECORD_ABSENT cites evidence '{evidence_id}' which cannot prove absence for '{case_u}'"
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
