"""Main executable entry point for HackerRank Orchestrate: Ghost Data Still Exists.

Runs the complete AI deletion audit agent:
1. Loads participant-facing dataset files.
2. Dispatches and indexes evidence (JSON, SQL, text/logs, PDF).
3. Resolves current and historical user identities.
4. Classifies request intent (handling non-deletion requests as NOT_APPLICABLE).
5. Assesses resource state against policy rules.
6. Synthesizes canonical remediation and verification steps.
7. Serializes and validates the final root output.csv.
"""

import argparse
import csv
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from code.config import (
    DELETION_REQUESTS_PATH,
    ROOT_OUTPUT_PATH,
    SAMPLE_DELETION_REQUESTS_PATH,
    STATUS_COMPLETE,
    STATUS_INCOMPLETE,
    STATUS_NOT_APPLICABLE,
)
from code.evidence.dispatcher import EvidenceDispatcher
from code.identity.resolver import IdentityResolver
from code.ingestion.csv_loader import (
    load_deletion_requests,
    load_deletion_rules,
    load_evidence_manifest,
    load_system_activities,
    load_user_audit_entries,
    load_user_identities,
)
from code.output.serializer import serialize_predictions_to_csv
from code.output.validator import validate_output_csv
from code.reasoning.decision_engine import DecisionEngine
from code.reasoning.policy_engine import PolicyEngine
from code.schemas import CasePrediction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ghost_data_audit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Ghost Data Still Exists Deletion Audit Agent."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=DELETION_REQUESTS_PATH,
        help="Path to deletion requests CSV (default: dataset/deletion_requests.csv)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=ROOT_OUTPUT_PATH,
        help="Path for output predictions CSV (default: output.csv at repo root)",
    )
    parser.add_argument(
        "--dataset-dir",
        "-d",
        type=Path,
        default=REPO_ROOT / "dataset",
        help="Path to dataset directory (default: dataset)",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run on sample deletion requests instead of full evaluation set",
    )
    return parser.parse_args()


def run_pipeline(
    input_path: Path,
    output_path: Path,
    dataset_dir: Path,
) -> List[CasePrediction]:
    start_time = time.time()
    logger.info("Initializing Deletion Audit Agent...")
    logger.info("Input requests: %s", input_path)
    logger.info("Output target: %s", output_path)

    # 1. Ingestion
    logger.info("Loading tabular datasets from %s...", dataset_dir)
    requests = load_deletion_requests(input_path)
    users = load_user_identities(dataset_dir / "user_identities.csv")
    audits = load_user_audit_entries(dataset_dir / "user_audit_log.csv")
    activities = load_system_activities(dataset_dir / "system_activity.csv")
    rules = load_deletion_rules(dataset_dir / "deletion_rules.csv")
    manifest_rows = list(csv.DictReader(open(dataset_dir / "evidence_files.csv", encoding="utf-8")))

    logger.info(
        "Loaded: %d requests, %d users, %d audit log entries, %d system activities, %d rules, %d evidence files.",
        len(requests),
        len(users),
        len(audits),
        len(activities),
        len(rules),
        len(manifest_rows),
    )

    # 2. Evidence Ingestion and Indexing
    logger.info("Extracting and indexing multi-modal evidence files...")
    dispatcher = EvidenceDispatcher(dataset_dir=dataset_dir)
    dispatcher.load_all(manifest_rows)
    logger.info(
        "Extracted %d structured records across %d evidence files.",
        len(dispatcher.records),
        len(manifest_rows),
    )

    # 3. Engine Initialization
    logger.info("Initializing Identity Resolver, Policy Engine, and Decision Engine...")
    resolver = IdentityResolver(users, audits)
    policy = PolicyEngine(rules)
    engine = DecisionEngine(resolver, policy, dispatcher, activities)

    # 4. Evaluation Loop
    logger.info("Auditing %d cases against point-in-time evidence...", len(requests))
    predictions: List[CasePrediction] = []
    status_counts = {
        STATUS_COMPLETE: 0,
        STATUS_INCOMPLETE: 0,
        STATUS_NOT_APPLICABLE: 0,
    }

    for idx, req in enumerate(requests, start=1):
        pred = engine.evaluate_case(req)
        predictions.append(pred)
        status_counts[pred.deletion_status] = status_counts.get(pred.deletion_status, 0) + 1
        if idx % 50 == 0 or idx == len(requests):
            logger.info("Processed %d / %d cases (%.1f%%)...", idx, len(requests), (idx / len(requests)) * 100)

    # 5. Serialization
    logger.info("Serializing predictions to %s...", output_path)
    serialize_predictions_to_csv(predictions, output_path)

    # 6. Strict Validation
    logger.info("Validating output compliance against problem contract...")
    expected_case_ids = [r.case_id for r in requests]
    is_valid, validation_errors = validate_output_csv(output_path, expected_case_ids=expected_case_ids)
    if not is_valid or validation_errors:
        logger.error("Validation failed with %d errors:", len(validation_errors))
        for err in validation_errors[:10]:
            logger.error("  - %s", err)
        raise ValueError(f"Output CSV validation failed with {len(validation_errors)} errors.")
    else:
        logger.info("Validation PASSED! Output perfectly conforms to all contract requirements.")

    elapsed = time.time() - start_time
    logger.info("Pipeline completed in %.2f seconds.", elapsed)
    logger.info("Results Summary:")
    logger.info("  Total Cases: %d", len(predictions))
    logger.info("  COMPLETE: %d", status_counts[STATUS_COMPLETE])
    logger.info("  INCOMPLETE: %d", status_counts[STATUS_INCOMPLETE])
    logger.info("  NOT_APPLICABLE: %d", status_counts[STATUS_NOT_APPLICABLE])

    return predictions


def main() -> None:
    args = parse_args()
    input_path = SAMPLE_DELETION_REQUESTS_PATH if args.sample else args.input
    output_path = args.output

    try:
        run_pipeline(
            input_path=input_path,
            output_path=output_path,
            dataset_dir=args.dataset_dir,
        )
    except Exception as e:
        logger.exception("Pipeline execution failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
