"""Unit tests for Canonical Step Ordering and Numbering."""

import unittest
from code.reasoning.policy_engine import RecordAssessment
from code.reasoning.remediation_planner import build_plan_from_assessments


class TestRemediationPlanner(unittest.TestCase):
    def test_canonical_phase_ordering(self):
        assessments = [
            RecordAssessment(
                system_id="support_platform",
                resource_id="support_001",
                data_category="SUPPORT_MESSAGE",
                required_action="REDACT",
                observed_state="PRESENT",
                is_violation=True,
                evidence_id="evidence_58",
                violation_operation="REPORT_EXPOSED_PII",
                remediation_operation="REDACT_RECORD",
                verification_operation="VERIFY_RECORD_REDACTED",
            ),
            RecordAssessment(
                system_id="integration_service",
                resource_id="data_flow_001",
                data_category="DATA_FLOW",
                required_action="DISABLE",
                observed_state="ACTIVE",
                is_violation=True,
                evidence_id="evidence_92",
                violation_operation="REPORT_ACTIVE_DATA_FLOW",
                remediation_operation="DISABLE_DATA_FLOW",
                verification_operation="VERIFY_DATA_FLOW_DISABLED",
            ),
        ]

        steps = build_plan_from_assessments(assessments, is_incomplete=True)

        # 1. Step numbers must be 1..N consecutively
        step_nos = [st.step_no for st in steps]
        self.assertEqual(step_nos, list(range(1, len(steps) + 1)))

        # 2. Phases must be FINDING -> REMEDIATION -> VERIFICATION
        phases = [st.phase for st in steps]
        self.assertEqual(phases[:2], ["FINDING", "FINDING"])
        self.assertEqual(phases[2:4], ["REMEDIATION", "REMEDIATION"])
        self.assertEqual(phases[4:], ["VERIFICATION", "VERIFICATION"])

        # 3. Operations within REMEDIATION: DISABLE_DATA_FLOW must come before REDACT_RECORD
        rem_ops = [st.operation for st in steps if st.phase == "REMEDIATION"]
        self.assertEqual(rem_ops, ["DISABLE_DATA_FLOW", "REDACT_RECORD"])

        # 4. Remediation and future verification must have empty evidence_id
        for st in steps:
            if st.phase in ("REMEDIATION", "VERIFICATION"):
                self.assertEqual(st.evidence_id, "")


if __name__ == "__main__":
    unittest.main()
