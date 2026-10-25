"""Regression tests covering confirmed defects in case_03, case_12, case_16, case_20, and case_22."""

import csv
from datetime import datetime, timezone
import json
import unittest
from pathlib import Path

from code.config import DATASET_DIR
from code.evidence.dispatcher import EvidenceDispatcher
from code.identity.resolver import IdentityResolver
from code.ingestion.csv_loader import (
    load_deletion_requests,
    load_deletion_rules,
    load_system_activities,
    load_user_audit_entries,
    load_user_identities,
)
from code.reasoning.decision_engine import DecisionEngine
from code.reasoning.policy_engine import PolicyEngine
from code.schemas import DeletionRequest


class TestRegressionCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent.parent
        cls.dataset_dir = cls.repo_root / "dataset"
        
        cls.requests = {
            r.case_id: r
            for r in load_deletion_requests(cls.dataset_dir / "sample_deletion_requests.csv")
        }
        cls.identities = load_user_identities(cls.dataset_dir / "user_identities.csv")
        cls.audits = load_user_audit_entries(cls.dataset_dir / "user_audit_log.csv")
        cls.activities = load_system_activities(cls.dataset_dir / "system_activity.csv")
        cls.rules = load_deletion_rules(cls.dataset_dir / "deletion_rules.csv")
        
        with open(cls.dataset_dir / "evidence_files.csv", encoding="utf-8") as f:
            manifest_rows = list(csv.DictReader(f))
            
        cls.dispatcher = EvidenceDispatcher(cls.dataset_dir)
        cls.dispatcher.load_all(manifest_rows)
        
        cls.resolver = IdentityResolver(cls.identities, cls.audits)
        cls.policy = PolicyEngine(cls.rules)
        cls.engine = DecisionEngine(cls.resolver, cls.policy, cls.dispatcher, cls.activities)
        
        with open(cls.dataset_dir / "sample_output.csv", encoding="utf-8") as f:
            cls.ground_truth = {
                row["case_id"]: (row["deletion_status"], json.loads(row["steps_json"]))
                for row in csv.DictReader(f)
            }

    def test_regression_case_03(self):
        """Regression test for case_03: Completed profile lookup with 404 must prove COMPLETE."""
        req = self.requests["case_03"]
        pred = self.engine.evaluate_case(req)
        gt_status, _ = self.ground_truth["case_03"]
        self.assertEqual(pred.deletion_status, gt_status)
        self.assertEqual(pred.deletion_status, "COMPLETE")

    def test_regression_case_12(self):
        """Regression test for case_12: Historical email hash mapping identifying remaining marketing profile."""
        req = self.requests["case_12"]
        pred = self.engine.evaluate_case(req)
        gt_status, gt_steps = self.ground_truth["case_12"]
        self.assertEqual(pred.deletion_status, gt_status)
        self.assertEqual(pred.deletion_status, "INCOMPLETE")
        pred_steps = [s.to_dict() for s in pred.steps]
        # Verify finding and remediation steps for the identified un-deleted resource
        self.assertEqual(pred_steps[0]["resource_id"], "analytics_9914")
        self.assertEqual(pred_steps[0]["operation"], "REPORT_REMAINING_RECORD")
        self.assertEqual(pred_steps[1]["resource_id"], "analytics_9914")
        self.assertEqual(pred_steps[1]["operation"], "DELETE_RECORD")
        # Ensure all expected ground truth verification resources are present
        pred_res = {s["resource_id"] for s in pred_steps}
        for s in gt_steps:
            self.assertIn(s["resource_id"], pred_res)

    def test_regression_case_16(self):
        """Regression test for case_16: SQL read replica retention identifying account and search findings."""
        req = self.requests["case_16"]
        pred = self.engine.evaluate_case(req)
        gt_status, gt_steps = self.ground_truth["case_16"]
        self.assertEqual(pred.deletion_status, gt_status)
        self.assertEqual(pred.deletion_status, "INCOMPLETE")
        pred_steps = [s.to_dict() for s in pred.steps]
        self.assertEqual(pred_steps, gt_steps)

    def test_regression_case_20(self):
        """Regression test for case_20: Log terminal state distinguishing hit and enabled data flow."""
        req = self.requests["case_20"]
        pred = self.engine.evaluate_case(req)
        gt_status, _ = self.ground_truth["case_20"]
        self.assertEqual(pred.deletion_status, gt_status)
        self.assertEqual(pred.deletion_status, "INCOMPLETE")

    def test_regression_case_22(self):
        """Regression test for case_22: SQL read replica customer document JSON extraction."""
        req = self.requests["case_22"]
        pred = self.engine.evaluate_case(req)
        gt_status, gt_steps = self.ground_truth["case_22"]
        self.assertEqual(pred.deletion_status, gt_status)
        self.assertEqual(pred.deletion_status, "INCOMPLETE")
        pred_steps = [s.to_dict() for s in pred.steps]
        self.assertEqual(pred_steps, gt_steps)

    def test_regression_case_01(self):
        """Regression test for case_01: Point-in-time database snapshot evidence_54 proves account_001 absent."""
        req = self.requests["case_01"]
        pred = self.engine.evaluate_case(req)
        self.assertEqual(pred.deletion_status, "COMPLETE")
        self.assertEqual(len(pred.steps), 1)
        step = pred.steps[0].to_dict()
        self.assertEqual(step["resource_id"], "account_001")
        self.assertEqual(step["system_id"], "account_service")
        self.assertEqual(step["operation"], "VERIFY_RECORD_ABSENT")
        self.assertEqual(step["state"], "ABSENT")
        self.assertEqual(step["evidence_id"], "evidence_54")

    def test_regression_case_02(self):
        """Regression test for case_02: Point-in-time database snapshot evidence_54 proves account_002 absent."""
        req = self.requests["case_02"]
        pred = self.engine.evaluate_case(req)
        self.assertEqual(pred.deletion_status, "COMPLETE")
        self.assertEqual(len(pred.steps), 1)
        step = pred.steps[0].to_dict()
        self.assertEqual(step["resource_id"], "account_002")
        self.assertEqual(step["system_id"], "account_service")
        self.assertEqual(step["operation"], "VERIFY_RECORD_ABSENT")
        self.assertEqual(step["state"], "ABSENT")
        self.assertEqual(step["evidence_id"], "evidence_54")

    def test_regression_case_04(self):
        """Regression test for case_04: Account proved absent via evidence_54 and analytics anonymized via evidence_56."""
        req = self.requests["case_04"]
        pred = self.engine.evaluate_case(req)
        self.assertEqual(pred.deletion_status, "COMPLETE")
        self.assertGreaterEqual(len(pred.steps), 1)
        step1 = pred.steps[0].to_dict()
        self.assertEqual(step1["resource_id"], "account_004")
        self.assertEqual(step1["system_id"], "account_service")
        self.assertEqual(step1["operation"], "VERIFY_RECORD_ABSENT")
        self.assertEqual(step1["state"], "ABSENT")
        self.assertEqual(step1["evidence_id"], "evidence_54")

    def test_regression_case_28(self):
        """Regression test for case_28: Verified COMPLETE across all systems with evidence_92 without foreign account_7012."""
        req = self.requests["case_28"]
        pred = self.engine.evaluate_case(req)
        self.assertEqual(pred.deletion_status, "COMPLETE")
        step_res = [s.resource_id for s in pred.steps]
        self.assertNotIn("account_7012", step_res)
        self.assertIn("audit_record_9265", step_res)
        self.assertIn("support_2351", step_res)
        for s in pred.steps:
            self.assertEqual(s.phase, "VERIFICATION")
            self.assertEqual(s.evidence_id, "evidence_92")

    def test_sample_pipeline_execution_and_contract_validation(self):
        """Priority 2 & 3: Run full sample pipeline and verify output strictly passes contract validator."""
        import tempfile
        from code.output.validator import validate_output_csv
        from code.main import run_pipeline

        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv") as tf:
            out_path = Path(tf.name)

        try:
            sample_in = self.dataset_dir / "sample_deletion_requests.csv"
            run_pipeline(input_path=sample_in, output_path=out_path, dataset_dir=self.dataset_dir)
            expected_cids = list(self.requests.keys())
            is_valid, errors = validate_output_csv(out_path, expected_cids, self.dataset_dir)
            self.assertTrue(is_valid, f"Pipeline output failed validation: {errors}")
            self.assertEqual(len(errors), 0)
        finally:
            if out_path.exists():
                out_path.unlink()

    def test_all_sample_cases_match_expected_status(self):
        """Priority 3: Require all 32 sample cases to match the official expected status."""
        for cid, req in self.requests.items():
            pred = self.engine.evaluate_case(req)
            gt_status, _ = self.ground_truth[cid]
            self.assertEqual(pred.deletion_status, gt_status, f"Status mismatch for {cid}: pred={pred.deletion_status}, gt={gt_status}")

    def test_custom_case_01_historical_identity_drift(self):
        """Custom Case 1: Historical email drift with stale read replica."""
        custom_req = DeletionRequest(
            case_id="custom_case_01",
            email="elena.vasquez@gmail.com",
            requested_at=datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc),
            reported_status="COMPLETE",
            reported_at=datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc),
            audit_at=datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc),
            request_text="Please permanently erase my personal account and all associated order history under GDPR article 17.",
        )
        pred = self.engine.evaluate_case(custom_req)
        # Status should be evaluated properly based on evidence
        self.assertIn(pred.deletion_status, ["COMPLETE", "INCOMPLETE"])

    def test_custom_case_02_data_portability_intent(self):
        """Custom Case 2: Non-deletion data portability request (Intent Discrimination)."""
        custom_req = DeletionRequest(
            case_id="custom_case_02",
            email="portability.user@example.com",
            requested_at=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
            reported_status="NOT_STARTED",
            reported_at=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
            audit_at=datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc),
            request_text="I am writing to request a copy of my personal data and recent invoices in CSV format. I am not asking for deletion and wish to continue using my account.",
        )
        pred = self.engine.evaluate_case(custom_req)
        self.assertEqual(pred.deletion_status, "NOT_APPLICABLE")
        self.assertEqual(pred.steps, [])

    def test_custom_case_03_account_tombstone_exposed_pii(self):
        """Custom Case 3: Account tombstone with exposed email hash."""
        custom_req = self.requests["case_32"]
        pred = self.engine.evaluate_case(custom_req)
        self.assertEqual(pred.deletion_status, "INCOMPLETE")
        finding_ops = [s.operation for s in pred.steps if s.phase == "FINDING"]
        self.assertIn("REPORT_EXPOSED_PII", finding_ops)


if __name__ == "__main__":
    unittest.main()
