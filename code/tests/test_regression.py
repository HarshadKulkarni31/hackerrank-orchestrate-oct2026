"""Regression tests covering confirmed defects in case_03, case_12, case_16, case_20, and case_22."""

import csv
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
        self.assertEqual(pred_steps, gt_steps)

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


if __name__ == "__main__":
    unittest.main()
