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

    def test_validator_rejects_irrelevant_evidence_system(self):
        # evidence_37 origin is security_service; citing it for account_service must be rejected
        steps_json = '[{"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_001", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_37"}]'
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8", newline="") as tf:
            writer = csv.writer(tf)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_01", "COMPLETE", steps_json])
            tf_path = Path(tf.name)

        is_valid, errors = validate_output_csv(tf_path, ["case_01"], Path("dataset"))
        self.assertFalse(is_valid)
        self.assertTrue(any("not relevant to system 'account_service'" in err for err in errors))

    def test_validator_rejects_mismatched_activity_resource(self):
        # activity_3342 targets account_001; citing it for account_9999 must be rejected
        steps_json = '[{"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_9999", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "activity_3342"}]'
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8", newline="") as tf:
            writer = csv.writer(tf)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_01", "COMPLETE", steps_json])
            tf_path = Path(tf.name)

        is_valid, errors = validate_output_csv(tf_path, ["case_01"], Path("dataset"))
        self.assertFalse(is_valid)
        self.assertTrue(any("concerns resource 'account_001', not claimed resource 'account_9999'" in err for err in errors))

    def test_validator_rejects_irrelevant_evidence_file_wrong_subject(self):
        # evidence_58 is support_001 for priya.raman / user_24; citing it for case_01 (user_01) must be rejected
        steps_json = '[{"step_no": 1, "phase": "FINDING", "system_id": "support_platform", "resource_id": "support_9999", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "evidence_58"}]'
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8", newline="") as tf:
            writer = csv.writer(tf)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_01", "INCOMPLETE", steps_json])
            tf_path = Path(tf.name)

        is_valid, errors = validate_output_csv(tf_path, ["case_01"], Path("dataset"))
        self.assertFalse(is_valid)
        self.assertTrue(any("does not contain claimed resource" in err for err in errors))

    def test_validator_rejects_irrelevant_activity_wrong_subject(self):
        # activity_4004 details mention user_18; citing it for case_01 (user_01) must be rejected
        steps_json = '[{"step_no": 1, "phase": "FINDING", "system_id": "export_service", "resource_id": "export_1260", "operation": "REPORT_REMAINING_RECORD", "state": "PRESENT", "evidence_id": "activity_4004"}]'
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8", newline="") as tf:
            writer = csv.writer(tf)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_01", "INCOMPLETE", steps_json])
            tf_path = Path(tf.name)

        is_valid, errors = validate_output_csv(tf_path, ["case_01"], Path("dataset"))
        self.assertFalse(is_valid)
        self.assertTrue(any("concerns subject 'user_18', not case subject 'user_01'" in err for err in errors))

    def test_validator_rejects_verify_record_absent_with_unrelated_evidence(self):
        # evidence_58 is for support_001 / priya.raman; citing it for VERIFY_RECORD_ABSENT on case_01 (user_01) must be rejected
        steps_json = '[{"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_001", "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_58"}]'
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv", encoding="utf-8", newline="") as tf:
            writer = csv.writer(tf)
            writer.writerow(["case_id", "deletion_status", "steps_json"])
            writer.writerow(["case_01", "COMPLETE", steps_json])
            tf_path = Path(tf.name)

        is_valid, errors = validate_output_csv(tf_path, ["case_01"], Path("dataset"))
        self.assertFalse(is_valid)
        self.assertTrue(any("does not contain claimed resource 'account_001' or subject 'user_01'" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
