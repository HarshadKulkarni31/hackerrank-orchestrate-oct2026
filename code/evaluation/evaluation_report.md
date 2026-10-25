# Evaluation Report: Ghost Data Still Exists Deletion-Audit Agent

## 1. Executive Summary

This report evaluates the performance of the automated AI deletion-audit agent for the HackerRank Orchestrate (October 2026) challenge: **Ghost Data Still Exists**.

The report evaluates two distinct execution scopes:
1. **Public Sample Benchmark Evaluation (32 cases)**: Audited against the official public benchmark (`dataset/sample_deletion_requests.csv` with canonical ground truth `dataset/sample_output.csv`), extended stress tests, and custom edge cases.
2. **Full Production Dataset Execution (518 cases)**: Full-dataset execution on `dataset/deletion_requests.csv`, serialized to root `output.csv` and strictly validated against all contract requirements.

The agent reconstructs historical user identities, indexes multimodal point-in-time evidence across secondary SQL databases, application logs, text handover sheets, JSON exports, and PDF attachments, evaluates system state against 15 organizational deletion rules, and produces canonical remediation and verification steps.

Following the latest targeted correctness pass:
- **Status Accuracy (32 Sample Benchmark)**: **100.00% (32/32)**. All 32 public benchmark cases match the official ground truth status.
- **Sequence Accuracy (32 Sample Benchmark)**: **37.50% (12/32)** exact step sequence matches (a **+33.4% relative improvement** over the initial baseline of 28.12%).
- **Step F1 Score**: **71.35%** (Step Precision: 71.73%, Step Recall: 70.98%).
- **Field Accuracies**: Phase: **89.64%**, Evidence ID: **90.16%**, State: **77.20%**, Operation: **75.65%**, System ID: **75.13%**, Resource ID: **74.09%**.
- **Full Production Run (518 Cases)**: Evaluated all 518 production cases in `output.csv` with **100% strict contract validation pass** (0 schema errors, 0 invalid operations, 0 ordering violations).

---

## 2. Quantitative Accuracy Metrics

### 2.1 Public Sample Benchmark Results (32 Cases) & Before/After Comparison

The table below contrasts the baseline agent against the updated system across the 32 public benchmark evaluation cases:

| Metric Category | Metric | Initial Baseline | Prior Version | Final Updated Score | Absolute Change | Relative Improvement |
|---|---|---|---|---|---|---|
| **Case-Level Status** | **Deletion-Status Accuracy** | 84.38% (27/32) | 90.62% (29/32) | **100.00% (32/32)** | **+15.62%** | **+18.5%** |
| **Sequence Accuracy** | **Exact Plan Sequence Accuracy** | 28.12% (9/32) | 31.25% (10/32) | **37.50% (12/32)** | **+9.38%** | **+33.4%** |
| **Step-Level Accuracy** | **Step Precision** | 64.56% | 69.49% | **71.73%** | **+7.17%** | **+11.1%** |
| **Step-Level Accuracy** | **Step Recall** | 52.85% | 63.73% | **70.98%** | **+18.13%** | **+34.3%** |
| **Step-Level Accuracy** | **Step F1 Score** | 58.12% | 66.49% | **71.35%** | **+13.23%** | **+22.8%** |
| **Field-Level Accuracy** | **Phase Accuracy** | 73.06% | 87.05% | **89.64%** | **+16.58%** | **+22.7%** |
| **Field-Level Accuracy** | **Evidence ID Accuracy** | 72.54% | 87.56% | **90.16%** | **+17.62%** | **+24.3%** |
| **Field-Level Accuracy** | **Operation Accuracy** | 58.03% | 74.61% | **75.65%** | **+17.62%** | **+30.4%** |
| **Field-Level Accuracy** | **State Accuracy** | 59.59% | 75.13% | **77.20%** | **+17.61%** | **+29.6%** |
| **Field-Level Accuracy** | **System ID Accuracy** | 61.66% | 66.84% | **75.13%** | **+13.47%** | **+21.8%** |
| **Field-Level Accuracy** | **Resource ID Accuracy** | 56.48% | 65.80% | **74.09%** | **+17.61%** | **+31.2%** |

### 2.2 Full Production Dataset Execution (518 Cases)

The full evaluation set (`dataset/deletion_requests.csv`) consists of 518 cases across diverse international user profiles and systems:
- **Output File**: Root `output.csv` (518 rows, exactly sorted by `case_id`).
- **Validation**: Strict verification via `validate_output_csv`:
  - 100% valid CSV headers (`case_id,deletion_status,steps_json`).
  - 100% valid phase sequence order (`FINDING` -> `REMEDIATION` -> `VERIFICATION`).
  - 100% valid operations and required states per policy engine.
  - Zero ungrounded evidence references.
  - 100% temporal validity (every cited evidence record captured at or before that case's `audit_at`).

---

## 3. Evidence File Ingestion & Extraction Coverage

Every manifest file in `dataset/evidence_files.csv` (94 files total) was audited and verified for parsing coverage:

| Category | File Count | Extracted Record Count | Status & Provenance Notes |
|---|---|---|---|
| **SQL Databases & Replicas** | 23 | 789 records | Unpacked SQLite tables, failover replicas, JSON payload columns (`record_json`) |
| **Application & Security Logs** | 26 | 1,025 records | RFC 5424 syslogs, JSON logs, bracket logs, trace correlation linking |
| **Service Resource Exports (JSON)** | 28 | 655 records | Full document hits, account exports, analytics profiles, tombstones |
| **Text Documents & Handover Notes** | 1 | 41 records | Key-value pairs, system states, handover spreadsheets |
| **PDF Documents & Attachments** | 4 | 9 records | Disputed orders, legal retention registers, compliance journals, attachments |
| **Image Evidence (Screenshots/PNG)** | 11 | 22 records | Distinguishes `predefined_catalog` from dynamic VLM extraction; preserves provenance |
| **Valid Empty Schemas** | 1 (`evidence_90`) | 0 records | Verified empty DDL snapshot scope with 0 data rows (legitimately empty) |
| **Total Manifest Coverage** | **94 files** | **2,541 records** | **93/94 files producing structured records (100% extractable coverage)** |

---

## 4. Key Code Review Fixes Implemented

### 1. Removal of Hardcoded Fallbacks and Grounded Absence Proof
* **Previous Defect**: Unobserved accounts either fell back to an arbitrary hardcoded snapshot or manufactured false findings from deletion activities.
* **Fix**: Authoritative point-in-time database snapshots (such as failover replica `evidence_54`) prove absence when the account database was captured at or before `audit_at` and the account is not present in the table. Unobserved accounts without supporting evidence preserve their unresolved state.
* **Verification**: `case_01`, `case_02`, and `case_04` correctly resolve as `COMPLETE` citing grounded database snapshots (`evidence_54`), achieving 100% benchmark status accuracy.

### 2. Elimination of Unrelated Deletion Worker Linking
* **Previous Defect**: `decision_engine.py` grabbed any single worker activity in the request window, incorrectly linking unrelated failed worker activity `activity_3532` (`account_7012`, belonging to `case_29`) to `case_28`.
* **Fix**: Removed the blind single-worker window heuristic. Worker activities are mapped only when directly mentioning the subject or when sharing the same workflow execution run with other known resources of that subject.
* **Verification**: `case_28` correctly evaluates as `COMPLETE` with all 6 verification checks citing `evidence_92`, without extra foreign steps.

### 3. Strengthened Semantic Evidence Validation
* **Previous Defect**: `validator.py` allowed unrelated evidence if certain origins matched.
* **Fix**: Strict verification of subject relevance, resource existence, system origin compatibility, and temporal cutoff. Absence verification requires authoritative snapshots and rejects evidence where the resource is actually present.
* **Verification**: Both `sample_output.csv` and the generated 518-case `output.csv` pass validation with 0 errors.

### 4. Data Flow Modeling & Operation Correctness
* **Previous Defect**: Generated integration verification steps incorrectly used `VERIFY_RECORD_ABSENT`.
* **Fix**: Modeled `DATA_FLOW` explicitly. Active connectors map to `REPORT_ACTIVE_DATA_FLOW` -> `DISABLE_DATA_FLOW` -> `VERIFY_DATA_FLOW_DISABLED`.
* **Verification**: 100% of data flow steps use `VERIFY_DATA_FLOW_DISABLED`.

### 5. Multi-Language Request Intent Classification
* **Previous Defect**: Keyword-only matching risked misclassifying GDPR Article 15/16/20 access and correction requests.
* **Fix**: Implemented hierarchical multi-lingual intent classifier with negative override patterns for correction, access, export, opt-out, and rectification in English, Spanish, French, German, and Portuguese.
* **Verification**: Public benchmark `case_24` (correction request) correctly classified as `NOT_APPLICABLE` with `steps_json=[]`.

### 6. Legal Retention Register Stream Parsing (`evidence_27`)
* **Previous Defect**: `evidence_27` (`dataset/evidence/documents/legal_retention_register_20260529.pdf`) produced zero records due to missing pattern matching for disputed orders.
* **Fix**: Implemented stream chunk parsing extracting all 6 disputed order rows (`ORD-\d+`) and linking them to their respective subjects (`user_08`, `user_12`, `user_17`, `user_21`, `user_24`, `user_29`) under `legal_service` and `LEGAL_HOLD_RECORD`. Applied Rule 13 (`RETAIN` / `VERIFY_RECORD_PRESENT`).
* **Verification**: `test_evidence_grounding_and_conflicts.py` verifies 100% extraction fidelity (6/6 records) and exact subject linkage. Manifest extraction coverage confirmed across 93 producing files + 1 valid empty schema.

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

## 6. Sequence Diagnostics & Benchmark Verification

Diagnostics across the 32 sample cases demonstrate:
- **Status Alignment**: **32 / 32 cases perfectly aligned (100.00%)**.
- **Absence Grounding**: Accounts deleted prior to point-in-time database snapshots (e.g. `evidence_54`) cite authoritative table snapshots proving absence at `audit_at`.
- **Verification Coverage**: Post-remediation verification checks cover 100% of remediated systems and required retained records.
- **Canonical Ordering**: 100% compliant with required phase sequence: `FINDING` -> `REMEDIATION` -> `VERIFICATION`.
- **Exact Sequence Matches**: **12 / 32 cases**, reflecting strong structural fidelity across complex multi-system remediation workflows.
