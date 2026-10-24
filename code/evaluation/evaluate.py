"""Evaluation script for computing benchmark accuracy against sample_output.csv.

Computes:
- Case-level deletion-status accuracy
- Step-level and field-level accuracy (phase, system_id, resource_id, operation, state, evidence_id)
- Sequence accuracy
- Custom evaluation cases evaluation
"""

import csv
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
DATASET_DIR = REPO_ROOT / "dataset"
SAMPLE_REQS_PATH = DATASET_DIR / "sample_deletion_requests.csv"
SAMPLE_OUTPUT_PATH = DATASET_DIR / "sample_output.csv"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("evaluator")


@dataclass
class EvalMetrics:
    total_cases: int
    correct_status: int
    status_accuracy: float
    total_expected_steps: int
    total_predicted_steps: int
    matched_steps: int
    step_precision: float
    step_recall: float
    step_f1: float
    exact_sequence_matches: int
    sequence_accuracy: float
    field_accuracies: Dict[str, float]


def evaluate_predictions(
    predictions: Dict[str, Tuple[str, List[Dict[str, Any]]]],
    ground_truth: Dict[str, Tuple[str, List[Dict[str, Any]]]],
) -> EvalMetrics:
    total_cases = len(ground_truth)
    correct_status = 0
    exact_sequences = 0

    total_exp_steps = 0
    total_pred_steps = 0
    matched_steps = 0

    field_counts = {
        "phase": 0,
        "system_id": 0,
        "resource_id": 0,
        "operation": 0,
        "state": 0,
        "evidence_id": 0,
    }
    field_matches = {k: 0 for k in field_counts}

    for case_id, (gt_status, gt_steps) in ground_truth.items():
        if case_id not in predictions:
            continue
        pred_status, pred_steps = predictions[case_id]

        # Case status
        if pred_status == gt_status:
            correct_status += 1

        # Sequence match
        if pred_status == gt_status and pred_steps == gt_steps:
            exact_sequences += 1

        total_exp_steps += len(gt_steps)
        total_pred_steps += len(pred_steps)

        # Field and step matching
        for idx, exp_step in enumerate(gt_steps):
            for field in field_counts:
                field_counts[field] += 1

            if idx < len(pred_steps):
                p_step = pred_steps[idx]
                step_exact = True
                for field in field_counts:
                    if p_step.get(field) == exp_step.get(field):
                        field_matches[field] += 1
                    else:
                        step_exact = False
                if step_exact:
                    matched_steps += 1

    status_acc = (correct_status / total_cases) * 100 if total_cases > 0 else 0.0
    seq_acc = (exact_sequences / total_cases) * 100 if total_cases > 0 else 0.0
    precision = (matched_steps / total_pred_steps) * 100 if total_pred_steps > 0 else 0.0
    recall = (matched_steps / total_exp_steps) * 100 if total_exp_steps > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    field_accs = {
        k: (field_matches[k] / field_counts[k]) * 100 if field_counts[k] > 0 else 0.0
        for k in field_counts
    }

    return EvalMetrics(
        total_cases=total_cases,
        correct_status=correct_status,
        status_accuracy=status_acc,
        total_expected_steps=total_exp_steps,
        total_predicted_steps=total_pred_steps,
        matched_steps=matched_steps,
        step_precision=precision,
        step_recall=recall,
        step_f1=f1,
        exact_sequence_matches=exact_sequences,
        sequence_accuracy=seq_acc,
        field_accuracies=field_accs,
    )


def load_csv_outputs(csv_path: Path) -> Dict[str, Tuple[str, List[Dict[str, Any]]]]:
    results = {}
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row["case_id"]
            status = row["deletion_status"]
            steps = json.loads(row["steps_json"])
            results[cid] = (status, steps)
    return results


def run_evaluation() -> EvalMetrics:
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
    from code.reasoning.decision_engine import DecisionEngine
    from code.reasoning.policy_engine import PolicyEngine

    requests = load_deletion_requests(SAMPLE_REQS_PATH)
    users = load_user_identities()
    audits = load_user_audit_entries()
    activities = load_system_activities()
    rules = load_deletion_rules()
    manifest_rows = list(csv.DictReader(open(DATASET_DIR / "evidence_files.csv", encoding="utf-8")))

    dispatcher = EvidenceDispatcher()
    dispatcher.load_all(manifest_rows)
    resolver = IdentityResolver(users, audits)
    policy = PolicyEngine(rules)
    engine = DecisionEngine(resolver, policy, dispatcher, activities)

    preds = {}
    for req in requests:
        p = engine.evaluate_case(req)
        preds[p.case_id] = (p.deletion_status, [st.to_dict() for st in p.steps])

    ground_truth = load_csv_outputs(SAMPLE_OUTPUT_PATH)
    metrics = evaluate_predictions(preds, ground_truth)

    logger.info("=== EVALUATION BENCHMARK RESULTS ===")
    logger.info("Total Cases: %d", metrics.total_cases)
    logger.info("Status Accuracy: %d / %d (%.2f%%)", metrics.correct_status, metrics.total_cases, metrics.status_accuracy)
    logger.info("Sequence Accuracy: %d / %d (%.2f%%)", metrics.exact_sequence_matches, metrics.total_cases, metrics.sequence_accuracy)
    logger.info("Step Precision: %.2f%%", metrics.step_precision)
    logger.info("Step Recall: %.2f%%", metrics.step_recall)
    logger.info("Step F1 Score: %.2f%%", metrics.step_f1)
    logger.info("Field-Level Accuracies:")
    for f, acc in metrics.field_accuracies.items():
        logger.info("  - %s: %.2f%%", f, acc)

    return metrics


if __name__ == "__main__":
    run_evaluation()
