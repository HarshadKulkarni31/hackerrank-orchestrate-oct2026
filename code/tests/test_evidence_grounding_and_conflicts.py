"""Unit and regression tests for evidence grounding, snapshot conflicts, absence verification, and provenance."""

import unittest
from datetime import datetime, timezone
from pathlib import Path

from code.evidence.dispatcher import EvidenceDispatcher, EvidenceRecord
from code.identity.resolver import IdentityResolver, UserIdentity, UserAuditEntry
from code.reasoning.decision_engine import DecisionEngine
from code.reasoning.policy_engine import PolicyEngine
from code.schemas import DeletionRequest, DeletionRule, SystemActivity
from code.config import STATUS_COMPLETE, STATUS_INCOMPLETE


class TestEvidenceGroundingAndConflicts(unittest.TestCase):
    def setUp(self):
        self.rules = [
            DeletionRule("R1", "USER_PROFILE", "None", "DELETE"),
            DeletionRule("R2", "ACCOUNT_TOMBSTONE", "None", "REDACT"),
            DeletionRule("R3", "SECURITY_AUDIT_LOG", "None", "RETAIN"),
            DeletionRule("R4", "DATA_FLOW", "None", "DISABLE"),
            DeletionRule("R5", "BACKUP_ARCHIVE", "None", "BLOCK"),
            DeletionRule("R6", "ANALYTICS_PROFILE", "None", "ANONYMIZE"),
        ]
        self.policy = PolicyEngine(self.rules)
        self.user = UserIdentity("user_test", "Test User", "test@example.com", "+1234567890", "hash123", datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.resolver = IdentityResolver([self.user], [])
        self.dispatcher = EvidenceDispatcher(Path("dataset"))

    def test_missing_account_evidence_cannot_become_complete(self):
        """Unobserved account with no snapshot evidence at audit_at cannot become COMPLETE or claim ABSENT."""
        req = DeletionRequest(
            case_id="case_missing_ev",
            email="test@example.com",
            requested_at=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
            reported_status="COMPLETE",
            reported_at=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
            audit_at=datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc),
            request_text="Please delete all my account data completely.",
        )
        # Empty dispatcher (no evidence)
        engine = DecisionEngine(self.resolver, self.policy, self.dispatcher, [])
        pred = engine.evaluate_case(req)

        self.assertEqual(pred.deletion_status, STATUS_INCOMPLETE)
        # Ensure no verification step claims absence with empty evidence
        for step in pred.steps:
            if step.phase == "VERIFICATION" and step.operation == "VERIFY_RECORD_ABSENT":
                self.fail("Engine must not produce an ungrounded VERIFY_RECORD_ABSENT when evidence is missing")

    def test_unrelated_snapshot_does_not_prove_absence(self):
        """A snapshot that does not cover the specific account cannot prove absence."""
        req = DeletionRequest(
            case_id="case_unrelated",
            email="test@example.com",
            requested_at=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
            reported_status="COMPLETE",
            reported_at=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
            audit_at=datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc),
            request_text="Delete my personal account and details.",
        )
        # Add snapshot that only covers account_9999 (completely different account)
        snap_rec = EvidenceRecord(
            evidence_id="evidence_unrelated",
            captured_at=datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc),
            system_id="account_service",
            resource_id="account_9999",
            data_category="USER_PROFILE",
            user_id="user_other",
            email="other@example.com",
            state="PRESENT",
        )
        self.dispatcher.records.append(snap_rec)
        self.dispatcher._by_resource["account_9999"] = [snap_rec]

        engine = DecisionEngine(self.resolver, self.policy, self.dispatcher, [])
        pred = engine.evaluate_case(req)

        # Must not fabricate evidence_unrelated for the test user
        for s in pred.steps:
            self.assertNotEqual(s.evidence_id, "evidence_unrelated")
        self.assertEqual(pred.deletion_status, STATUS_INCOMPLETE)

    def test_conflicting_snapshots_detect_replication_drift(self):
        """When primary shows ABSENT but replica shows PRESENT, replication drift is flagged."""
        req = DeletionRequest(
            case_id="case_drift",
            email="test@example.com",
            requested_at=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
            reported_status="COMPLETE",
            reported_at=datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc),
            audit_at=datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc),
            request_text="I want my account deleted.",
        )
        # Primary lookup shows ABSENT (404)
        rec_absent = EvidenceRecord(
            evidence_id="evidence_lookup",
            captured_at=datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc),
            system_id="account_service",
            resource_id="account_test",
            data_category="USER_PROFILE",
            user_id=None,
            email=None,
            state="ABSENT",
        )
        # Failover replica snapshot shows PRESENT (drift!)
        rec_present = EvidenceRecord(
            evidence_id="evidence_replica",
            captured_at=datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc),
            system_id="account_service",
            resource_id="account_test",
            data_category="USER_PROFILE",
            user_id="user_test",
            email="test@example.com",
            state="PRESENT",
        )
        self.dispatcher.records.extend([rec_absent, rec_present])
        self.dispatcher._by_resource["account_test"] = [rec_absent, rec_present]
        self.dispatcher._by_user["user_test"] = [rec_present]

        engine = DecisionEngine(self.resolver, self.policy, self.dispatcher, [])
        pred = engine.evaluate_case(req)

        # Must be flagged as INCOMPLETE with a finding step
        self.assertEqual(pred.deletion_status, STATUS_INCOMPLETE)
        finding_ops = [s.operation for s in pred.steps if s.phase == "FINDING"]
        self.assertIn("REPORT_REMAINING_RECORD", finding_ops)

    def test_resource_with_no_matching_records_preserves_unresolved(self):
        """Candidate resource with zero matching evidence records is not marked absent."""
        ass = self.policy.assess_record(
            system_id="account_service",
            resource_id="account_ghost",
            data_category="USER_PROFILE",
            observed_state="UNRESOLVED",
            evidence_id="",
        )
        self.assertTrue(ass.is_violation)
        self.assertEqual(ass.observed_state, "PRESENT")

    def test_image_extraction_provenance_distinguishes_catalog_from_dynamic(self):
        """EvidenceRecord and EvidenceDispatcher accurately record extraction_method."""
        disp = EvidenceDispatcher(Path("dataset"))
        disp._parse_image("evidence_04", datetime(2026, 9, 26, 11, 0, tzinfo=timezone.utc), Path("dataset/evidence/images/evidence_04.png"), origin="admin_console")
        self.assertIn("evidence_04", disp.file_provenance)
        self.assertEqual(disp.file_provenance["evidence_04"]["extraction_method"], "predefined_catalog")
        for rec in disp.records:
            if rec.evidence_id == "evidence_04":
                self.assertEqual(rec.extraction_method, "predefined_catalog")

    def test_missing_catalog_image_and_api_unavailable_behavior(self):
        """Image not in catalog with no API key is handled gracefully as unsupported."""
        import os
        disp = EvidenceDispatcher(Path("dataset"))
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        try:
            method = disp._parse_image("evidence_999_fake", datetime(2026, 9, 26, 11, 0, tzinfo=timezone.utc), Path("fake_screenshot.png"), origin="admin_console")
            self.assertEqual(method, "unsupported")
            self.assertIn("evidence_999_fake", disp.file_provenance)
            self.assertEqual(disp.file_provenance["evidence_999_fake"]["status"], "UNSUPPORTED_FORMAT")
        finally:
            if old_key:
                os.environ["GEMINI_API_KEY"] = old_key


if __name__ == "__main__":
    unittest.main()
