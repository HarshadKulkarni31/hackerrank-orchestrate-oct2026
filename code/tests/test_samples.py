"""Integration tests against public sample dataset."""

import csv
import json
import unittest
from pathlib import Path

from code.config import SAMPLE_DELETION_REQUESTS_PATH, SAMPLE_OUTPUT_PATH
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


class TestPublicSamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dataset_dir = Path("dataset")
        cls.requests = load_deletion_requests(SAMPLE_DELETION_REQUESTS_PATH)
        cls.users = load_user_identities(dataset_dir / "user_identities.csv")
        cls.audits = load_user_audit_entries(dataset_dir / "user_audit_log.csv")
        cls.activities = load_system_activities(dataset_dir / "system_activity.csv")
        cls.rules = load_deletion_rules(dataset_dir / "deletion_rules.csv")
        with open(dataset_dir / "evidence_files.csv", encoding="utf-8") as f:
            cls.manifest = list(csv.DictReader(f))

        cls.dispatcher = EvidenceDispatcher(dataset_dir=dataset_dir)
        cls.dispatcher.load_all(cls.manifest)
        cls.resolver = IdentityResolver(cls.users, cls.audits)
        cls.policy = PolicyEngine(cls.rules)
        cls.engine = DecisionEngine(cls.resolver, cls.policy, cls.dispatcher, cls.activities)

    def test_samples_status_accuracy_threshold(self):
        with open(SAMPLE_OUTPUT_PATH, encoding="utf-8") as f:
            ground_truth = {
                r["case_id"]: r["deletion_status"]
                for r in csv.DictReader(f)
            }

        correct = 0
        for req in self.requests:
            pred = self.engine.evaluate_case(req)
            if pred.deletion_status == ground_truth[req.case_id]:
                correct += 1

        acc = (correct / len(self.requests)) * 100
        # Benchmark status accuracy should exceed 80%
        self.assertGreaterEqual(acc, 80.0, f"Status accuracy was {acc:.2f}%, expected >= 80%")


if __name__ == "__main__":
    unittest.main()
