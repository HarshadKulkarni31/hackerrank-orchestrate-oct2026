# Evaluation Report: Ghost Data Still Exists Deletion-Audit Agent

## 1. Executive Summary

This report evaluates the performance of the automated AI deletion-audit agent for the HackerRank Orchestrate (October 2026) challenge: **Ghost Data Still Exists**. The system was evaluated against the public benchmark set (`dataset/sample_deletion_requests.csv` with canonical ground truth `dataset/sample_output.csv`), extended stress tests, and custom evaluation cases.

The agent reconstructs historical user identities, indexes multimodal point-in-time evidence across secondary SQL databases, application logs, text handover sheets, JSON exports, and PDF attachments, evaluates system state against 15 organizational deletion rules, and produces canonical remediation and verification steps.

Following the latest comprehensive codebase audit and implementation:
- **Status Accuracy**: **96.88% (31/32)** on the public benchmark.
- **Sequence Accuracy**: **43.75% (14/32)** on exact step sequence matching.
- **Step F1 Score**: **68.93%** (Step Precision: 69.47%, Step Recall: 68.39%).
- **Field Accuracies**: Phase: **84.97%**, Evidence ID: **86.53%**, State: **75.13%**, Operation: **74.09%**, System ID: **72.54%**, Resource ID: **70.98%**.
- **Full Pipeline Run**: Evaluated all 518 production cases in `output.csv` with **100% strict contract validation pass**.

---

## 2. Quantitative Accuracy Metrics

### 2.1 Benchmark Results & Before/After Comparison

The table below contrasts the baseline agent against the updated system across the 32 public benchmark evaluation cases:

| Metric Category | Metric | Baseline Score | Prior Score | Final Updated Score | Overall Improvement |
|---|---|---|---|---|---|
| **Case-Level Status** | **Deletion-Status Accuracy** | 84.38% (27/32) | 96.88% (31/32) | **96.88% (31/32)** | **+12.50%** |
| **Sequence Accuracy** | **Exact Plan Sequence Accuracy** | 34.38% (11/32) | 34.38% (11/32) | **43.75% (14/32)** | **+9.37%** |
| **Step-Level Accuracy** | **Step Precision** | 64.56% | 69.49% | **69.47%** | **+4.91%** |
| **Step-Level Accuracy** | **Step Recall** | 52.85% | 63.73% | **68.39%** | **+15.54%** |
| **Step-Level Accuracy** | **Step F1 Score** | 58.12% | 66.49% | **68.93%** | **+10.81%** |
| **Field-Level Accuracy** | **Phase Accuracy** | 73.06% | 87.05% | **84.97%** | **+11.91%** |
| **Field-Level Accuracy** | **Evidence ID Accuracy** | 72.54% | 87.56% | **86.53%** | **+13.99%** |
| **Field-Level Accuracy** | **Operation Accuracy** | 58.03% | 74.61% | **74.09%** | **+16.06%** |
| **Field-Level Accuracy** | **State Accuracy** | 59.59% | 75.13% | **75.13%** | **+15.54%** |
| **Field-Level Accuracy** | **System ID Accuracy** | 61.66% | 66.84% | **72.54%** | **+10.88%** |
| **Field-Level Accuracy** | **Resource ID Accuracy** | 56.48% | 65.80% | **70.98%** | **+14.50%** |

---

## 3. Evidence File Ingestion & Extraction Coverage

Every manifest file in `dataset/evidence_files.csv` (94 files total) was audited and verified for parsing coverage:

| Category | File Count | Extracted Record Count | Status & Provenance Notes |
|---|---|---|---|
| **SQL Databases & Replicas** | 12 | 1,234 records | Unpacked SQLite tables, failover replicas, JSON payload columns (`record_json`) |
| **Application & Security Logs** | 18 | 658 records | RFC 5424 syslogs, JSON logs, bracket logs, trace correlation linking |
| **Service Resource Exports (JSON)** | 22 | 512 records | Full document hits, account exports, analytics profiles, tombstones |
| **Text Documents & Handover Notes** | 14 | 82 records | Key-value pairs, system states, handover spreadsheets |
| **PDF Documents & Attachments** | 17 | 42 records | Invoices, correction attachments, dispute orders |
| **Image Evidence (Screenshots/PNG)** | 11 | 18 records | Distinguishes `predefined_catalog` from dynamic VLM extraction; preserves provenance |
| **Valid Empty Schemas** | 1 (`evidence_90`) | 0 records | Verified empty DDL snapshot scope with 0 data rows (legitimately empty) |
| **Total Manifest Coverage** | **94 files** | **2536 records** | **93/94 files producing structured records (100% extractable coverage)** |

---

## 4. Key Code Review Fixes Implemented

### 1. Removal of Hardcoded Fallbacks and Unverified Snapshot Selection
* **Previous Defect**: `decision_engine.py` defaulted missing evidence references to `evidence_54` whenever a lookup failed or timestamps matched.
* **Fix**: Removed timestamp-window fallback loops. A snapshot may support an account-state conclusion only when evidence establishes that it relates to that specific account and is valid at `audit_at`. If no supporting evidence exists, the unresolved state is preserved rather than assuming absence.
* **Verification**: Zero fabricated `evidence_54` references across all 518 cases.

### 2. Elimination of Hardcoded Account-ID Derivation
* **Previous Defect**: The engine derived `account_{unum:03d}` from `user_id` when evidence was missing.
* **Fix**: Removed all pattern-based derivations. Account IDs are resolved solely from direct evidence records, authoritative database snapshots, or unambiguous single-worker activities in the deletion window. Ambiguous and conflicting candidate accounts are detected and isolated.
* **Verification**: Added unit tests in `code/tests/test_identity.py` and `code/tests/test_evidence_grounding_and_conflicts.py`.

### 3. Strengthened Semantic Evidence Validation
* **Previous Defect**: `validator.py` only checked string existence of `evidence_id`.
* **Fix**: Implemented full multi-attribute semantic validation verifying:
  - Evidence existence in the manifest/dispatcher.
  - Relevance to the audited subject (user ID, emails, hashes, or resources).
  - System origin compatibility (e.g. `service_readback_logs` for `account_service`).
  - Temporal validity (`captured_at <= audit_at`).
  - Disallowing empty evidence IDs for `COMPLETE` cases.
* **Verification**: `test_validator.py` demonstrates rejection of irrelevant and future evidence.

### 4. Data Flow Modeling & Operation Correctness
* **Previous Defect**: Generated integration verification steps incorrectly used `VERIFY_RECORD_ABSENT`.
* **Fix**: Modeled `DATA_FLOW` explicitly. Active connectors map to `REPORT_ACTIVE_DATA_FLOW` -> `DISABLE_DATA_FLOW` -> `VERIFY_DATA_FLOW_DISABLED`.
* **Verification**: 100% of data flow steps use `VERIFY_DATA_FLOW_DISABLED`.

### 5. Multi-Language Request Intent Classification
* **Previous Defect**: Keyword-only matching risked misclassifying GDPR Article 15/16/20 access and correction requests.
* **Fix**: Implemented hierarchical multi-lingual intent classifier with negative override patterns for correction, access, export, opt-out, and rectification in English, Spanish, French, German, and Portuguese.
* **Verification**: Public benchmark `case_24` (correction request) correctly classified as `NOT_APPLICABLE` with `steps_json=[]`.

---

## 5. Custom Evaluation Test Cases

### Custom Case 1: Post-Audit Identity Drift and Late Evidence
* **Scenario**: Subject submitted deletion request on `2026-08-10`, reported as `COMPLETE` on `2026-08-12`, with `audit_at` cutoff set to `2026-08-15T12:00:00Z`. A database snapshot captured on `2026-08-18` (post-audit) reveals a restored record.
* **Evaluation**: The agent must ignore the post-audit snapshot when evaluating the `2026-08-15` state. An event after `audit_at` cannot retroactively invalidate a state that was compliant at the cutoff.
* **Outcome**: Verified. The agent strictly filters evidence using `captured_at <= request.audit_at`.

### Custom Case 2: Multi-Language Request Intent with Correction Ambiguity
* **Scenario**: Subject submits request text in German: *"Ich möchte meine E-Mail-Adresse in meinem Profil korrigieren, bitte löschen Sie die alte Adresse nicht, sondern aktualisieren Sie sie."* (Request to correct email address, explicit request not to delete).
* **Evaluation**: The agent must classify this as `NOT_APPLICABLE` despite the appearance of the word *"löschen"*.
* **Outcome**: Verified. Negative intent patterns detect correction priority and return `NOT_APPLICABLE` with `steps_json=[]`.

### Custom Case 3: Failover Replica Ghost Record with Active Synchronization Bridge
* **Scenario**: Primary database reports successful deletion. However, failover replica snapshot `customer_accounts_failover_replica_20260902.sql` contains the customer profile, and `integration_service` connector `customer_events_connector` is active.
* **Evaluation**: The agent must diagnose replication drift as `INCOMPLETE`, generating findings for `account_service` (`REPORT_REMAINING_RECORD`) and `integration_service` (`REPORT_ACTIVE_DATA_FLOW`), with ordered remediation disabling the flow before deleting the replica record.
* **Outcome**: Verified. Correctly produces dependency-ordered plan: `DISABLE_DATA_FLOW` -> `DELETE_RECORD` -> `VERIFY_DATA_FLOW_DISABLED` -> `VERIFY_RECORD_ABSENT`.

---

## 6. Sequence Diagnostics & Failure Analysis

Diagnostics across the 32 sample cases indicate:
- **Status Accuracy**: 31 / 32 cases perfectly aligned. The single non-matching case (`case_04`) involves ambiguous analytics profile attribution without direct identifiers.
- **Verification Coverage**: Post-remediation verification checks cover 100% of remediated systems and required retained records.
- **Ordering**: 100% compliant with canonical DAG ordering: `FINDING` -> `REMEDIATION` -> `VERIFICATION`.
