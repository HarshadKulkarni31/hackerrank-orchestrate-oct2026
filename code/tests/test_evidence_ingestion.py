import csv
import unittest
from pathlib import Path

from code.evidence.dispatcher import EvidenceDispatcher, IMAGE_EVIDENCE_CATALOG


class TestEvidenceIngestion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dispatcher = EvidenceDispatcher()
        manifest_path = Path("dataset/evidence_files.csv")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_rows = list(csv.DictReader(f))
        cls.dispatcher.load_all(manifest_rows)

    def test_image_consoles_ingestion(self):
        """Test that all 11 PNG administrative consoles are parsed into structured records."""
        self.assertEqual(len(self.dispatcher.unsupported_files), 0, "No evidence files should be unsupported")
        self.assertGreaterEqual(len(self.dispatcher.records), 2500)

        # Verify key image files are present in records
        expected_image_ids = {
            "evidence_04", "evidence_09", "evidence_14", "evidence_19",
            "evidence_23", "evidence_28", "evidence_32", "evidence_37",
            "evidence_42", "evidence_46", "evidence_60"
        }
        extracted_evidence_ids = {r.evidence_id for r in self.dispatcher.records}
        for eid in expected_image_ids:
            self.assertIn(eid, extracted_evidence_ids, f"Image {eid} must have extracted records")

    def test_image_record_attributes(self):
        """Test specific image records have correct system, resource, and state mappings."""
        # evidence_14: active connector data flow
        rec_14 = [r for r in self.dispatcher.records if r.evidence_id == "evidence_14" and r.resource_id == "data_flow_1121"]
        self.assertEqual(len(rec_14), 1)
        self.assertEqual(rec_14[0].system_id, "integration_service")
        self.assertEqual(rec_14[0].data_category, "DATA_FLOW")
        self.assertEqual(rec_14[0].state, "ACTIVE")

        # evidence_32: active backup restore entry
        rec_32 = [r for r in self.dispatcher.records if r.evidence_id == "evidence_32" and r.resource_id == "backup_9287"]
        self.assertEqual(len(rec_32), 1)
        self.assertEqual(rec_32[0].system_id, "backup_service")
        self.assertEqual(rec_32[0].data_category, "BACKUP_ARCHIVE")
        self.assertEqual(rec_32[0].state, "ACTIVE")

        # evidence_42: redacted tombstone
        rec_42 = [r for r in self.dispatcher.records if r.evidence_id == "evidence_42" and r.resource_id == "user_17"]
        self.assertEqual(len(rec_42), 1)
        self.assertEqual(rec_42[0].system_id, "identity_service")
        self.assertEqual(rec_42[0].state, "REDACTED")
        self.assertFalse(rec_42[0].has_exposed_pii)

    def test_manifest_coverage(self):
        """Test that at least 93 of 94 manifest files produce evidence records."""
        with open("dataset/evidence_files.csv", "r", encoding="utf-8") as f:
            manifest_rows = list(csv.DictReader(f))
        all_file_ids = {m["file_id"] for m in manifest_rows}
        active_file_ids = {r.evidence_id for r in self.dispatcher.records}
        unparsed = all_file_ids - active_file_ids

        # Only evidence_90 (empty database schema without data inserts) should have 0 records
        self.assertEqual(unparsed, {"evidence_90"})
        self.assertEqual(len(active_file_ids), 93)


if __name__ == "__main__":
    unittest.main()
