# Ghost Data Still Exists: Codebase Documentation

This directory contains the runnable source code, reasoning engines, evidence parsers, evaluation suites, and diagnostic interfaces for the **Ghost Data Still Exists** AI deletion-audit agent.

## Package Architecture

```text
code/
├── main.py                     # Official pipeline entry point (audits all 518 cases)
├── config.py                   # Central paths, allowed phases, operations, and state maps
├── schemas.py                  # Dataclasses (CasePrediction, Step, IdentityBundle, etc.)
├── ingestion/
│   ├── csv_loader.py           # Fast typed CSV loader for requests, identities, rules, activity
│   └── __init__.py
├── identity/
│   ├── resolver.py             # Reconstructs current and historical user identities up to cutoff
│   └── __init__.py
├── evidence/
│   ├── dispatcher.py           # Multi-modal evidence indexing across 94 files (JSON, SQL, logs, PDF)
│   ├── parse_json.py           # Service exports and snapshot bundle parser
│   ├── parse_sqlite.py         # SQLite table snapshot and replica extractor
│   ├── parse_text_logs.py      # System event logs and handover sheet parser
│   ├── parse_pdf.py            # Stream decoder (ASCII85 / Flate) for support attachments
│   └── __init__.py
├── reasoning/
│   ├── request_classifier.py   # Intent classifier (detecting non-deletion NOT_APPLICABLE cases)
│   ├── policy_engine.py        # Evaluates 15 deletion rules, PII exposure, and tombstone requirements
│   ├── remediation_planner.py  # Enforces canonical step ordering and consecutive numbering
│   ├── decision_engine.py      # Unified auditor tying identity, evidence, activity, and policy
│   └── __init__.py
├── output/
│   ├── serializer.py           # RFC-compliant CSV writer preserving consecutive step order
│   ├── validator.py            # Strict schema and semantic checker against challenge rules
│   └── __init__.py
├── evaluation/
│   ├── evaluate.py             # Quantitative benchmark accuracy calculator
│   ├── main.py                 # Evaluation runner entry point
│   ├── evaluation_report.md    # Metric breakdown and 3 custom evaluation cases
│   └── usage_report.md         # Model and deterministic execution telemetry
├── prompts/
│   ├── request_intent.md       # Prompt template for intent classification
│   ├── evidence_extraction.md  # Guidelines for extracting records from evidence artifacts
│   └── conflict_resolution.md  # Multi-replica conflict resolution guidelines
├── tests/
│   ├── test_identity.py        # Identity resolution unit tests
│   ├── test_policy.py          # Policy engine and deletion rules unit tests
│   ├── test_ordering.py        # Canonical step ordering unit tests
│   ├── test_serialization.py   # Output CSV formatting and validation tests
│   └── test_samples.py         # Public sample cases integration tests
└── ui/
    ├── app.py                  # Lightweight diagnostic audit web workbench (zero external deps)
    └── __init__.py
```

## Running the Code

1. **Full Evaluation Run**:
   ```bash
   python code/main.py
   ```
2. **Sample Verification Run**:
   ```bash
   python code/main.py --sample --output output_sample.csv
   ```
3. **Run Unit Tests**:
   ```bash
   python -m unittest discover -s code/tests
   ```
4. **Run Benchmark Evaluation**:
   ```bash
   python code/evaluation/main.py
   ```
5. **Launch Diagnostic UI Workbench**:
   ```bash
   python code/ui/app.py 8080
   # Open http://localhost:8080 in browser
   ```
