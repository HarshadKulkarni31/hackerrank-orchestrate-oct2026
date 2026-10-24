"""Entry point for running evaluation suite."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from code.evaluation.evaluate import run_evaluation

if __name__ == "__main__":
    run_evaluation()
