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

REMEDIATION_OP_ORDER = {
    "DISABLE_DATA_FLOW": 0,
    "BLOCK_RESTORE": 1,
    "DELETE_RECORD": 2,
    "REDACT_RECORD": 3,
    "ANONYMIZE_RECORD": 4,
}

VERIFICATION_OP_ORDER = {
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
            op_val = FINDING_OP_ORDER.get(s.operation, 99)
        elif s.phase == "REMEDIATION":
            op_val = REMEDIATION_OP_ORDER.get(s.operation, 99)
        else:
            op_val = VERIFICATION_OP_ORDER.get(s.operation, 99)
        return (p_val, op_val, s.system_id, s.resource_id)

    sorted_list = sorted(steps, key=sort_key)
    # Assign consecutive step numbers 1..N
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
