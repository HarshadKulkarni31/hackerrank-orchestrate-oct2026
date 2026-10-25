"""Unit tests for PolicyEngine and Deletion Rules."""

import unittest
from code.reasoning.policy_engine import PolicyEngine
from code.schemas import DeletionRule


class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.rules = [
            DeletionRule("R1", "USER_PROFILE", "Always", "DELETE"),
            DeletionRule("R2", "SUPPORT_MESSAGE", "Conversation contains shared context", "REDACT"),
            DeletionRule("R3", "ANALYTICS_PROFILE", "Record is still attributable", "ANONYMIZE"),
            DeletionRule("R4", "SECURITY_AUDIT_LOG", "Within retention period", "RETAIN"),
            DeletionRule("R5", "ACCOUNT_TOMBSTONE", "Deleted account needs stable user reference", "REDACT"),
        ]
        self.policy = PolicyEngine(self.rules)

    def test_user_profile_deletion_violation(self):
        ass = self.policy.assess_record(
            system_id="account_service",
            resource_id="account_001",
            data_category="USER_PROFILE",
            observed_state="PRESENT",
            evidence_id="evidence_54",
        )
        self.assertTrue(ass.is_violation)
        self.assertEqual(ass.violation_operation, "REPORT_REMAINING_RECORD")
        self.assertEqual(ass.remediation_operation, "DELETE_RECORD")
        self.assertEqual(ass.verification_operation, "VERIFY_RECORD_ABSENT")

    def test_user_profile_compliant_absent(self):
        ass = self.policy.assess_record(
            system_id="account_service",
            resource_id="account_001",
            data_category="USER_PROFILE",
            observed_state="ABSENT",
            evidence_id="evidence_54",
        )
        self.assertFalse(ass.is_violation)
        self.assertIsNone(ass.violation_operation)
        self.assertEqual(ass.verification_operation, "VERIFY_RECORD_ABSENT")

    def test_tombstone_exposed_pii_violation(self):
        ass = self.policy.assess_record(
            system_id="identity_service",
            resource_id="tombstone_9178",
            data_category="ACCOUNT_TOMBSTONE",
            observed_state="PRESENT",
            evidence_id="evidence_51",
            has_exposed_pii=True,
        )
        self.assertTrue(ass.is_violation)
        self.assertEqual(ass.violation_operation, "REPORT_EXPOSED_PII")
        self.assertEqual(ass.remediation_operation, "REDACT_RECORD")
        self.assertEqual(ass.verification_operation, "VERIFY_RECORD_REDACTED")

    def test_security_audit_retained_compliant(self):
        ass = self.policy.assess_record(
            system_id="security_service",
            resource_id="audit_record_2016",
            data_category="SECURITY_AUDIT_LOG",
            observed_state="PRESENT",
            evidence_id="evidence_94",
        )
        self.assertFalse(ass.is_violation)
        self.assertIsNone(ass.violation_operation)
        self.assertEqual(ass.verification_operation, "VERIFY_RECORD_PRESENT")

    def test_data_flow_active_violation(self):
        ass = self.policy.assess_record(
            system_id="integration_service",
            resource_id="data_flow_1234",
            data_category="DATA_FLOW",
            observed_state="ACTIVE",
            evidence_id="evidence_03",
            is_active_flow=True,
        )
        self.assertTrue(ass.is_violation)
        self.assertEqual(ass.violation_operation, "REPORT_ACTIVE_DATA_FLOW")
        self.assertEqual(ass.remediation_operation, "DISABLE_DATA_FLOW")
        self.assertEqual(ass.verification_operation, "VERIFY_DATA_FLOW_DISABLED")

    def test_backup_restore_risk_violation(self):
        ass = self.policy.assess_record(
            system_id="backup_service",
            resource_id="backup_5678",
            data_category="BACKUP_ARCHIVE",
            observed_state="ACTIVE",
            evidence_id="evidence_93",
            is_restore_risk=True,
        )
        self.assertTrue(ass.is_violation)
        self.assertEqual(ass.violation_operation, "REPORT_RESTORE_RISK")
        self.assertEqual(ass.remediation_operation, "BLOCK_RESTORE")
        self.assertEqual(ass.verification_operation, "VERIFY_RESTORE_BLOCKED")

    def test_unsupported_category_handling(self):
        ass = self.policy.assess_record(
            system_id="mystery_service",
            resource_id="mystery_001",
            data_category="UNKNOWN_CATEGORY",
            observed_state="PRESENT",
            evidence_id="evidence_01",
        )
        self.assertTrue(ass.is_violation)
        self.assertEqual(ass.required_action, "UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
