"""Unit tests for Output Serialization and Validation."""

import json
import tempfile
import unittest
from pathlib import Path

from code.output.serializer import serialize_predictions_to_csv
from code.output.validator import validate_output_csv
from code.schemas import CasePrediction, Step


class TestSerialization(unittest.TestCase):
    def test_serialize_and_validate_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "output.csv"
            preds = [
                CasePrediction(
                    case_id="case_001",
                    deletion_status="COMPLETE",
                    steps=[
                        Step(1, "VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "ABSENT", "evidence_54")
                    ],
                ),
                CasePrediction(
                    case_id="case_002",
                    deletion_status="NOT_APPLICABLE",
                    steps=[],
                ),
            ]

            serialize_predictions_to_csv(preds, out_path)
            self.assertTrue(out_path.exists())

            # Validate against strict contract
            is_valid, errors = validate_output_csv(out_path, expected_case_ids=["case_001", "case_002"])
            self.assertTrue(is_valid)
            self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
