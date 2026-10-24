"""Serializes predictions into output.csv matching official challenge contract."""

import csv
import json
from pathlib import Path
from typing import List

from code.schemas import CasePrediction, Step
from code.config import ROOT_OUTPUT_PATH


def serialize_step(step: Step) -> dict:
    return {
        "step_no": step.step_no,
        "phase": step.phase,
        "system_id": step.system_id,
        "resource_id": step.resource_id,
        "operation": step.operation,
        "state": step.state,
        "evidence_id": step.evidence_id,
    }


def serialize_predictions_to_csv(
    predictions: List[CasePrediction], output_path: Path = ROOT_OUTPUT_PATH
) -> None:
    # Sort lexicographically by case_id
    sorted_preds = sorted(predictions, key=lambda p: p.case_id)

    with open(output_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["case_id", "deletion_status", "steps_json"])
        for p in sorted_preds:
            if p.deletion_status == "NOT_APPLICABLE":
                steps_json_str = "[]"
            else:
                serialized_steps = [serialize_step(s) for s in p.steps]
                steps_json_str = json.dumps(serialized_steps, separators=(",", ":"))
            writer.writerow([p.case_id, p.deletion_status, steps_json_str])
