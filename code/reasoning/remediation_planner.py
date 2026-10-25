"""Remediation and verification sequence planner."""

from typing import List, Dict, Any
from code.schemas import Step
from code.reasoning.policy_engine import RecordAssessment
from code.config import VALID_OPERATION_STATES

FINDING_OP_ORDER = {
    "REPORT_REMAINING_RECORD": 0,
    "REPORT_EXPOSED_PII": 1,
    "REPORT_ACTIVE_DATA_FLOW": 2,
    "REPORT_RESTORE_RISK": 3,
}

SYSTEM_FINDING_ORDER = {
    "account_service": 0,
    "search_service": 1,
    "export_service": 2,
    "support_platform": 3,
    "analytics_platform": 4,
    "identity_service": 5,
    "integration_service": 6,
    "backup_service": 7,
}

REMEDIATION_OP_ORDER = {
    "DISABLE_DATA_FLOW": 0,
    "BLOCK_RESTORE": 1,
    "DELETE_RECORD": 2,
    "REDACT_RECORD": 3,
    "ANONYMIZE_RECORD": 4,
}

SYSTEM_REMEDIATION_ORDER = {
    "integration_service": 0,
    "backup_service": 1,
    "account_service": 2,
    "search_service": 3,
    "export_service": 4,
    "support_platform": 5,
    "identity_service": 6,
    "analytics_platform": 7,
}

SYSTEM_VERIFY_ORDER = {
    "account_service": 0,
    "search_service": 1,
    "export_service": 2,
    "security_service": 3,
    "support_platform": 4,
    "identity_service": 4,
    "analytics_platform": 5,
    "integration_service": 6,
    "backup_service": 7,
}

VERIFY_OP_ORDER = {
    "VERIFY_RECORD_ABSENT": 0,
    "VERIFY_RECORD_PRESENT": 1,
    "VERIFY_RECORD_REDACTED": 2,
    "VERIFY_RECORD_ANONYMIZED": 3,
    "VERIFY_DATA_FLOW_DISABLED": 4,
    "VERIFY_RESTORE_BLOCKED": 5,
}


def sort_steps_canonically(steps: List[Step]) -> List[Step]:
    """Sorts steps deterministically by phase, operation priority, system_id, resource_id."""
    phase_order_map = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}

    def sort_key(s: Step):
        p_val = phase_order_map.get(s.phase, 99)
        if s.phase == "FINDING":
            return (
                p_val,
                FINDING_OP_ORDER.get(s.operation, 99),
                SYSTEM_FINDING_ORDER.get(s.system_id, 99),
                s.resource_id,
            )
        elif s.phase == "REMEDIATION":
            return (
                p_val,
                REMEDIATION_OP_ORDER.get(s.operation, 99),
                SYSTEM_REMEDIATION_ORDER.get(s.system_id, 99),
                s.resource_id,
            )
        else:
            return (
                p_val,
                VERIFY_OP_ORDER.get(s.operation, 99),
                SYSTEM_VERIFY_ORDER.get(s.system_id, 99),
                s.resource_id,
            )

    sorted_list = sorted(steps, key=sort_key)
    for i, s in enumerate(sorted_list, start=1):
        s.step_no = i
    return sorted_list


def build_plan_from_assessments(
    assessments: List[RecordAssessment], is_incomplete: bool
) -> List[Step]:
    """Builds a complete, canonically ordered list of steps from record assessments."""
    steps: List[Step] = []

    if is_incomplete:
        # 1. Findings for violations
        for a in assessments:
            if a.is_violation and a.violation_operation:
                state = VALID_OPERATION_STATES[a.violation_operation]
                steps.append(
                    Step(
                        step_no=0,
                        phase="FINDING",
                        system_id=a.system_id,
                        resource_id=a.resource_id,
                        operation=a.violation_operation,
                        state=state,
                        evidence_id=a.evidence_id,
                    )
                )

        # 2. Remediation actions for violations (evidence_id must be "")
        for a in assessments:
            if a.is_violation and a.remediation_operation:
                state = VALID_OPERATION_STATES[a.remediation_operation]
                steps.append(
                    Step(
                        step_no=0,
                        phase="REMEDIATION",
                        system_id=a.system_id,
                        resource_id=a.resource_id,
                        operation=a.remediation_operation,
                        state=state,
                        evidence_id="",
                    )
                )

        # 3. Post-remediation verification checks (evidence_id must be "")
        for a in assessments:
            if a.verification_operation:
                state = VALID_OPERATION_STATES[a.verification_operation]
                steps.append(
                    Step(
                        step_no=0,
                        phase="VERIFICATION",
                        system_id=a.system_id,
                        resource_id=a.resource_id,
                        operation=a.verification_operation,
                        state=state,
                        evidence_id="",
                    )
                )

    else:
        # COMPLETE: only verification steps proving compliant current state
        for a in assessments:
            if a.verification_operation:
                state = VALID_OPERATION_STATES[a.verification_operation]
                steps.append(
                    Step(
                        step_no=0,
                        phase="VERIFICATION",
                        system_id=a.system_id,
                        resource_id=a.resource_id,
                        operation=a.verification_operation,
                        state=state,
                        evidence_id=a.evidence_id,
                    )
                )

    return sort_steps_canonically(steps)
