"""Unit tests for semantic Output CSV Validator."""

import csv
import io
from pathlib import Path
import tempfile
import unittest

from code.output.validator import validate_output_csv


class TestOutputValidator(unittest.TestCase):
    def test_validator_rejects_nonexistent_evidence_id(self):
        steps_json = '[{"step_no": 1, "phase": "FINDING", "system_id": "account_service", "resource_id": "account_001", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "fake_evidence_999"}]'
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8", newline="") as tf:
            writer = csv.writer(tf)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_01", "INCOMPLETE", steps_json])
            tf_path = Path(tf.name)

        is_valid, errors = validate_output_csv(tf_path, ["case_01"], Path("dataset"))
        self.assertFalse(is_valid)
        self.assertTrue(any("does not exist in participant evidence files" in err for err in errors))

    def test_validator_rejects_subsystem_operation_mismatch(self):
        steps_json = '[{"step_no": 1, "phase": "VERIFICATION", "system_id": "integration_service", "resource_id": "data_flow_01", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_03"}]'
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8", newline="") as tf:
            writer = csv.writer(tf)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_01", "COMPLETE", steps_json])
            tf_path = Path(tf.name)

        is_valid, errors = validate_output_csv(tf_path, ["case_01"], Path("dataset"))
        self.assertFalse(is_valid)
        self.assertTrue(any("VERIFY_DATA_FLOW_DISABLED" in err for err in errors))

    def test_validator_rejects_future_evidence_captured_after_audit_at(self):
        # case_168 has audit_at 2026-07-28; evidence_16 was captured on 2026-07-30
        steps_json = '[{"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_8748", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_16"}]'
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8", newline="") as tf:
            writer = csv.writer(tf)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_168", "COMPLETE", steps_json])
            tf_path = Path(tf.name)

        is_valid, errors = validate_output_csv(tf_path, ["case_168"], Path("dataset"))
        self.assertFalse(is_valid)
        self.assertTrue(any("is AFTER case audit_at" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
